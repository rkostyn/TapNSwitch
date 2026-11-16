"""Running an event's stages: swiss schedule, late entries, standings, bracket.

``app.services.tournament`` holds the pure pairing/standings/bracket logic;
this module loads and stores what that logic needs. Errors are raised as
``app.services.errors`` domain errors with the API's detail messages.
"""
from datetime import UTC, datetime

from app.db.mongo import MongoClient
from app.logger import get_logger
from app.models.event import Event, EventType, SwissStanding, default_pairing_style
from app.models.match import Match
from app.models.throw import ThrowsGet
from app.repositories.documents import new_match_document
from app.repositories.event_repository import EventRepository, event_type_condition
from app.repositories.match_repository import MatchRepository
from app.repositories.throw_repository import ThrowRepository
from app.services.errors import ConflictError, LockedError, NotFoundError
from app.services.tournament import (
    GHOST_PLAYER_ID,
    build_bracket_matches,
    build_group_pairings,
    build_late_entry_pairings,
    compute_swiss_standings,
    late_entry_quota,
)
from app.venue import lanes_for_arena_ids

logger = get_logger(__name__)


def swiss_lane_ids(event: Event) -> list[str] | None:
    """Which lanes group-stage matches are dealt onto, or None to leave them
    unassigned. Tournament events deal them onto the event's lanes; standard
    (everyday) events do not.
    """
    return lanes_for_arena_ids(event.arena_ids) if event.event_type == "tournament" else None


async def get_event_or_404(repo: EventRepository, event_id: str) -> Event:
    event = await repo.get_event(event_id)
    if not event:
        raise NotFoundError("Event not found")
    return event


async def get_open_event(repo: EventRepository, event_id: str) -> Event:
    event = await get_event_or_404(repo, event_id)
    if event.is_finished:
        raise LockedError("Event is finished")
    return event


def swiss_match_docs(
    event_id: str,
    pairings: list[tuple[str, str]],
    rounds_per_match: int,
    now: datetime,
    start_sequence: int = 1,
    lane_ids: list[str] | None = None,
) -> list[dict]:
    """Match documents for a swiss schedule. With ``lane_ids`` (even empty),
    each match gets an ``arena_id``, dealt round-robin onto the lanes."""
    docs = []
    for i, (p1, p2) in enumerate(pairings):
        extra = {}
        if lane_ids is not None:
            extra["arena_id"] = lane_ids[i % len(lane_ids)] if lane_ids else None
        docs.append(new_match_document(
            event_id=event_id,
            player_1_id=p1,
            player_2_id=p2,
            sequence=start_sequence + i,
            match_type="swiss",
            rounds_per_match=rounds_per_match,
            now=now,
            **extra,
        ))
    return docs


async def swiss_played(mongo_client: MongoClient, event_id: str, swiss_match_ids: set[str]) -> bool:
    """Whether any throw has been recorded in the event's swiss matches. Once
    play starts, the schedule is extended rather than rebuilt."""
    if not swiss_match_ids:
        return False
    throws = await ThrowRepository(mongo_client).get_throws_by_criteria(ThrowsGet(event_id=event_id))
    return any(t.match_id in swiss_match_ids for t in throws)


async def update_swiss_config(mongo_client: MongoClient, event_id: str, fields: dict) -> Event:
    repo = EventRepository(mongo_client)
    event = await get_open_event(repo, event_id)
    if event.bracket_generated_at:
        raise ConflictError("Bracket already generated")
    existing = await MatchRepository(mongo_client).get_matches_by_event(event_id, match_type="swiss")
    if await swiss_played(mongo_client, event_id, {m.match_id for m in existing}):
        raise ConflictError("Swiss scores already recorded")
    return await repo.update_event_fields(event_id, fields)


async def set_event_type(mongo_client: MongoClient, event_id: str, event_type: EventType) -> Event:
    """Change an event's type until its matches are generated. The pairing
    style resets to the new type's default; setting the current type is a
    no-op.

    Race safety: the type is written in one conditional update that only
    applies while the event is open and no group stage or bracket has been
    generated, and swiss generation only marks itself done while the event
    still has the type it built the schedule for (otherwise it removes its
    matches and answers 409). A manually created match does not touch the
    event, so one created between the match check and the write can still
    slip through.
    """
    repo = EventRepository(mongo_client)
    event = await get_open_event(repo, event_id)
    if event.event_type == event_type:
        return event
    if event.bracket_generated_at or event.swiss_generated_at:
        raise ConflictError("Matches already generated; the event type can no longer change")
    if await MatchRepository(mongo_client).event_has_matches(event_id):
        raise ConflictError("The event already has matches; the event type can no longer change")
    updated = await repo.set_event_type(
        event_id, event.event_type, event_type, default_pairing_style(event_type)
    )
    if updated is not None:
        logger.info("Event %s type changed from %s to %s", event_id, event.event_type, event_type)
        return updated
    # The event changed between the read and the write; report its state now.
    current = await get_open_event(repo, event_id)
    if current.event_type == event_type:
        return current
    raise ConflictError("Matches already generated; the event type can no longer change")


async def generate_swiss_matches(mongo_client: MongoClient, event_id: str) -> list[Match]:
    """Build the swiss (or round robin) schedule from the roster. Before any
    score is recorded the schedule is rebuilt from scratch; after, only players
    added since get new games."""
    repo = EventRepository(mongo_client)
    event = await get_open_event(repo, event_id)
    if event.bracket_generated_at:
        raise ConflictError("Bracket already generated; swiss matches are locked")
    if len(event.players) < 2:
        raise ConflictError("At least 2 players are required")
    match_repo = MatchRepository(mongo_client)
    existing = await match_repo.get_matches_by_event(event_id, match_type="swiss")
    now = datetime.now(UTC)

    if existing and await swiss_played(mongo_client, event_id, {m.match_id for m in existing}):
        return await _schedule_late_entrants(repo, match_repo, event, existing, now)

    if existing:
        await match_repo.delete_matches_by_event(event_id, match_type="swiss")
    pairings = build_group_pairings(
        event.pairing_style, event.players, event.late_players, event.swiss_matches_per_player
    )
    docs = swiss_match_docs(
        event_id, pairings, event.swiss_rounds_per_match, now, lane_ids=swiss_lane_ids(event),
    )
    matches = await match_repo.insert_matches(docs)
    # Conditional on the type the schedule was built for: if the type was
    # switched while we were building, the new matches do not belong to it.
    marked = await repo.update_event_fields_where(
        event_id,
        event_type_condition(event.event_type),
        {"swiss_generated_at": now, "swiss_standings": None, "standings_generated_at": None},
    )
    if marked is None:
        await match_repo.delete_matches([m.match_id for m in matches])
        raise ConflictError("Event type changed while generating matches; try again")
    logger.info("Generated %d swiss matches for event %s", len(matches), event_id)
    return matches


async def _schedule_late_entrants(
    repo: EventRepository,
    match_repo: MatchRepository,
    event: Event,
    existing: list[Match],
    now: datetime,
) -> list[Match]:
    """Keep the scored matches and only schedule games for players added since,
    so a late entrant can still join the swiss stage."""
    scheduled = {
        p for m in existing for p in (m.player_1_id, m.player_2_id)
        if p and p != GHOST_PLAYER_ID
    }
    new_players = [p for p in event.players if p not in scheduled]
    if not new_players:
        return existing
    pairings = build_late_entry_pairings(
        event.players, new_players, event.late_players,
        late_entry_quota(event.pairing_style, len(event.players), event.swiss_matches_per_player),
        [(m.player_1_id, m.player_2_id) for m in existing],
    )
    start_sequence = max((m.sequence for m in existing), default=0) + 1
    docs = swiss_match_docs(
        event.event_id, pairings, event.swiss_rounds_per_match, now, start_sequence,
        swiss_lane_ids(event),
    )
    added = await match_repo.insert_matches(docs)
    # New games make the stored standings stale until recomputed.
    await repo.update_event_fields(
        event.event_id, {"swiss_standings": None, "standings_generated_at": None}
    )
    logger.info("Added %d swiss matches for %d late entrant(s) in event %s",
                len(added), len(new_players), event.event_id)
    return existing + added


async def generate_swiss_standings(mongo_client: MongoClient, event_id: str) -> list[dict]:
    repo = EventRepository(mongo_client)
    event = await get_event_or_404(repo, event_id)
    swiss_matches = await MatchRepository(mongo_client).get_matches_by_event(event_id, match_type="swiss")
    if not swiss_matches:
        raise ConflictError("No swiss matches generated yet")
    throws = await ThrowRepository(mongo_client).get_throws_by_criteria(ThrowsGet(event_id=event_id))
    standings = compute_swiss_standings(event.players, {m.match_id for m in swiss_matches}, throws)
    await repo.update_event_fields(
        event_id,
        {"swiss_standings": standings, "standings_generated_at": datetime.now(UTC)},
    )
    logger.info("Generated swiss standings for event %s", event_id)
    return standings


async def get_standings(mongo_client: MongoClient, event_id: str) -> list[SwissStanding]:
    event = await get_event_or_404(EventRepository(mongo_client), event_id)
    if event.swiss_standings is None:
        raise NotFoundError("Standings not generated yet")
    return event.swiss_standings


async def generate_bracket(mongo_client: MongoClient, event_id: str, rounds_per_match: int) -> list[Match]:
    repo = EventRepository(mongo_client)
    event = await get_open_event(repo, event_id)
    if event.bracket_generated_at:
        raise ConflictError("Bracket already generated")
    if not event.swiss_standings:
        raise ConflictError("Generate swiss scores before building the bracket")
    match_repo = MatchRepository(mongo_client)
    existing = await match_repo.get_matches_by_event(event_id)
    seeds = [s.player for s in event.swiss_standings]
    docs = build_bracket_matches(seeds, event_id, rounds_per_match, start_sequence=len(existing) + 1)
    matches = await match_repo.insert_matches(docs)
    await repo.update_event_fields(
        event_id,
        {"bracket_generated_at": datetime.now(UTC), "bracket_rounds_per_match": rounds_per_match},
    )
    logger.info("Generated bracket with %d matches for event %s", len(matches), event_id)
    return matches


async def get_bracket(mongo_client: MongoClient, event_id: str) -> list[Match]:
    await get_event_or_404(EventRepository(mongo_client), event_id)
    return await MatchRepository(mongo_client).get_matches_by_event(event_id, match_type="bracket")
