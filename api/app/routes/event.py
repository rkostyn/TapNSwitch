import uuid
from datetime import UTC, datetime
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query
from app.db.mongo import MongoClient
from app.dependencies import get_mongo_client, get_current_user, rate_limit
from app.repositories.event_repository import EventRepository
from app.repositories.match_repository import MatchRepository
from app.repositories.throw_repository import ThrowRepository
from app.repositories.venue_repository import VenueRepository
from app.models.event import (
    BracketGenerate,
    Event,
    EventArenasUpdate,
    EventCreate,
    LateUpdate,
    PlayerAdd,
    SwissConfigUpdate,
    SwissStanding,
)
from app.models.match import Match
from app.models.throw import ThrowsGet
from app.services.tournament import (
    GHOST_PLAYER_ID,
    build_bracket_matches,
    build_late_entry_pairings,
    build_swiss_pairings,
    compute_swiss_standings,
)
from app.logger import get_logger
from app.services.event_filters import venue_timezone

logger = get_logger(__name__)

router = APIRouter(prefix="/event", tags=["Events"])


async def _default_arena_ids(mongo_client: MongoClient) -> list[str]:
    arenas = await VenueRepository(mongo_client).get_arenas()
    return [arena.id for arena in arenas]


async def _validate_event_arena_ids(mongo_client: MongoClient, arena_ids: list[str]) -> None:
    allowed = {arena.id for arena in await VenueRepository(mongo_client).get_arenas()}
    unknown = [arena_id for arena_id in arena_ids if arena_id not in allowed]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown arena id(s): {', '.join(unknown)}")


@router.post("", response_model=Event)
async def create_event(
    body: EventCreate,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    logger.info("Creating event")
    repo = EventRepository(mongo_client)
    event = await repo.create_event(body, current_user)
    arena_ids = await _default_arena_ids(mongo_client)
    updated = await repo.update_event_fields(event.event_id, {"arena_ids": arena_ids})
    return updated or event


@router.get("", response_model=list[Event])
async def list_events(
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
    date: date_type | None = Query(
        default=None,
        description="Booking date (YYYY-MM-DD) in venue timezone; defaults to today",
    ),
    q: str | None = Query(default=None, min_length=1, max_length=128, description="Search name, code, or player"),
):
    booking_date = date or datetime.now(venue_timezone()).date()
    logger.info("Listing events for user %s on %s (q=%s)", current_user, booking_date, q)
    repo = EventRepository(mongo_client)
    return await repo.get_events_by_user(current_user, booking_date=booking_date, search=q)


@router.get("/checkfront/active", response_model=list[Event])
async def list_active_checkfront_events(
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
    date: date_type | None = Query(
        default=None,
        description="Booking date (YYYY-MM-DD) in venue timezone; defaults to today",
    ),
    q: str | None = Query(default=None, min_length=1, max_length=128, description="Search name, code, or player"),
):
    """Open Checkfront-imported groups for today's floor — used for the group picker."""
    booking_date = date or datetime.now(venue_timezone()).date()
    repo = EventRepository(mongo_client)
    return await repo.get_active_checkfront_events(booking_date=booking_date, search=q)


@router.get("/{event_id}", response_model=Event, dependencies=[Depends(rate_limit(60))])
async def get_event(
    event_id: str,
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    logger.info("Fetching event %s", event_id)
    repo = EventRepository(mongo_client)
    result = await repo.get_event(event_id)
    if not result:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.delete("/{event_id}", status_code=204)
async def delete_event(
    event_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    if not await repo.delete_event(event_id):
        raise HTTPException(status_code=404, detail="Event not found")


@router.post("/{event_id}/finish", response_model=Event)
async def finish_event(
    event_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    existing = await repo.get_event(event_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")
    if existing.is_finished:
        raise HTTPException(status_code=423, detail="Event is already finished")
    result = await repo.finish_event(event_id)
    if not result:
        raise HTTPException(status_code=423, detail="Event is already finished")
    return result


async def _get_open_event(repo: EventRepository, event_id: str) -> Event:
    event = await repo.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.is_finished:
        raise HTTPException(status_code=423, detail="Event is finished")
    return event


async def _swiss_played(mongo_client: MongoClient, event_id: str, swiss_match_ids: set[str]) -> bool:
    """Whether any throw has been recorded in the event's swiss matches. Used to
    protect results: once play starts, the schedule is extended rather than
    rebuilt."""
    if not swiss_match_ids:
        return False
    throw_repo = ThrowRepository(mongo_client)
    throws = await throw_repo.get_throws_by_criteria(ThrowsGet(event_id=event_id))
    return any(t.match_id in swiss_match_ids for t in throws)


def _swiss_match_docs(event_id, pairings, rounds_per_match, now, start_sequence=1, arena_ids=None):
    lanes = arena_ids or []
    docs = []
    for i, (p1, p2) in enumerate(pairings):
        docs.append(
            {
                "match_id": str(uuid.uuid4()),
                "event_id": event_id,
                "player_1_id": p1,
                "player_2_id": p2,
                "sequence": start_sequence + i,
                "match_type": "swiss",
                "rounds_per_match": rounds_per_match,
                "bracket_round": None,
                "bracket_slot": None,
                "winner_id": None,
                "timestamp": now,
                "is_locked": False,
                "locked_by": None,
                "locked_at": None,
                "is_finished": False,
                "finished_at": None,
                "arena_id": lanes[i % len(lanes)] if lanes else None,
            }
        )
    return docs


@router.post("/{event_id}/player", response_model=Event)
async def add_player(
    event_id: str,
    body: PlayerAdd,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    await _get_open_event(repo, event_id)
    try:
        result = await repo.add_player(event_id, body.player_name)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.delete("/{event_id}/player/{player_name}", response_model=Event)
async def remove_player(
    event_id: str,
    player_name: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    await _get_open_event(repo, event_id)
    try:
        result = await repo.remove_player(event_id, player_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.put("/{event_id}/player/{player_name}/late", response_model=Event)
async def set_player_late(
    event_id: str,
    player_name: str,
    body: LateUpdate,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    await _get_open_event(repo, event_id)
    try:
        result = await repo.set_player_late(event_id, player_name, body.late)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.put("/{event_id}/arenas", response_model=Event)
async def update_event_arenas(
    event_id: str,
    body: EventArenasUpdate,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    await _validate_event_arena_ids(mongo_client, body.arena_ids)
    repo = EventRepository(mongo_client)
    await _get_open_event(repo, event_id)
    updated = await repo.update_event_fields(event_id, {"arena_ids": body.arena_ids})
    if not updated:
        raise HTTPException(status_code=404, detail="Event not found")
    return updated


@router.put("/{event_id}/swiss-config", response_model=Event)
async def update_swiss_config(
    event_id: str,
    body: SwissConfigUpdate,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    event = await _get_open_event(repo, event_id)
    if event.bracket_generated_at:
        raise HTTPException(status_code=409, detail="Bracket already generated")
    match_repo = MatchRepository(mongo_client)
    existing = await match_repo.get_matches_by_event(event_id, match_type="swiss")
    if await _swiss_played(mongo_client, event_id, {m.match_id for m in existing}):
        raise HTTPException(status_code=409, detail="Swiss scores already recorded")
    return await repo.update_event_fields(event_id, body.model_dump())


@router.post("/{event_id}/swiss/generate", response_model=list[Match])
async def generate_swiss_matches(
    event_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    event = await _get_open_event(repo, event_id)
    if event.bracket_generated_at:
        raise HTTPException(status_code=409, detail="Bracket already generated; swiss matches are locked")
    if len(event.players) < 2:
        raise HTTPException(status_code=409, detail="At least 2 players are required")
    match_repo = MatchRepository(mongo_client)
    existing = await match_repo.get_matches_by_event(event_id, match_type="swiss")
    now = datetime.now(UTC)

    if existing and await _swiss_played(mongo_client, event_id, {m.match_id for m in existing}):
        # Play has started — keep the scored matches and only schedule games for
        # players added since, so a late entrant can still join the swiss stage.
        scheduled = {
            p for m in existing for p in (m.player_1_id, m.player_2_id)
            if p and p != GHOST_PLAYER_ID
        }
        new_players = [p for p in event.players if p not in scheduled]
        if not new_players:
            return existing
        pairings = build_late_entry_pairings(
            event.players, new_players, event.late_players,
            event.swiss_matches_per_player,
            [(m.player_1_id, m.player_2_id) for m in existing],
        )
        start_sequence = max((m.sequence for m in existing), default=0) + 1
        docs = _swiss_match_docs(
            event_id, pairings, event.swiss_rounds_per_match, now, start_sequence, event.arena_ids
        )
        added = await match_repo.insert_matches(docs)
        # New games make the stored standings stale until recomputed.
        await repo.update_event_fields(
            event_id, {"swiss_standings": None, "standings_generated_at": None}
        )
        logger.info("Added %d swiss matches for %d late entrant(s) in event %s",
                    len(added), len(new_players), event_id)
        return existing + added

    # No scores yet — (re)build the whole schedule from the current roster.
    if existing:
        await match_repo.delete_matches_by_event(event_id, match_type="swiss")
    pairings = build_swiss_pairings(event.players, event.late_players, event.swiss_matches_per_player)
    docs = _swiss_match_docs(event_id, pairings, event.swiss_rounds_per_match, now, arena_ids=event.arena_ids)
    matches = await match_repo.insert_matches(docs)
    await repo.update_event_fields(
        event_id,
        {"swiss_generated_at": now, "swiss_standings": None, "standings_generated_at": None},
    )
    logger.info("Generated %d swiss matches for event %s", len(matches), event_id)
    return matches


@router.post("/{event_id}/swiss/scores", response_model=list[SwissStanding])
async def generate_swiss_scores(
    event_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    event = await repo.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    match_repo = MatchRepository(mongo_client)
    swiss_matches = await match_repo.get_matches_by_event(event_id, match_type="swiss")
    if not swiss_matches:
        raise HTTPException(status_code=409, detail="No swiss matches generated yet")
    throw_repo = ThrowRepository(mongo_client)
    throws = await throw_repo.get_throws_by_criteria(ThrowsGet(event_id=event_id))
    standings = compute_swiss_standings(
        event.players, {m.match_id for m in swiss_matches}, throws
    )
    await repo.update_event_fields(
        event_id,
        {"swiss_standings": standings, "standings_generated_at": datetime.now(UTC)},
    )
    logger.info("Generated swiss standings for event %s", event_id)
    return standings


@router.get("/{event_id}/standings", response_model=list[SwissStanding], dependencies=[Depends(rate_limit(60))])
async def get_standings(
    event_id: str,
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    event = await repo.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.swiss_standings is None:
        raise HTTPException(status_code=404, detail="Standings not generated yet")
    return event.swiss_standings


@router.post("/{event_id}/bracket/generate", response_model=list[Match])
async def generate_bracket(
    event_id: str,
    body: BracketGenerate,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    event = await _get_open_event(repo, event_id)
    if event.bracket_generated_at:
        raise HTTPException(status_code=409, detail="Bracket already generated")
    if not event.swiss_standings:
        raise HTTPException(status_code=409, detail="Generate swiss scores before building the bracket")
    match_repo = MatchRepository(mongo_client)
    existing = await match_repo.get_matches_by_event(event_id)
    seeds = [s.player for s in event.swiss_standings]
    docs = build_bracket_matches(
        seeds, event_id, body.rounds_per_match, start_sequence=len(existing) + 1
    )
    matches = await match_repo.insert_matches(docs)
    await repo.update_event_fields(
        event_id,
        {"bracket_generated_at": datetime.now(UTC), "bracket_rounds_per_match": body.rounds_per_match},
    )
    logger.info("Generated bracket with %d matches for event %s", len(matches), event_id)
    return matches


@router.get("/{event_id}/bracket", response_model=list[Match], dependencies=[Depends(rate_limit(60))])
async def get_bracket(
    event_id: str,
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    event = await repo.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    match_repo = MatchRepository(mongo_client)
    return await match_repo.get_matches_by_event(event_id, match_type="bracket")


@router.post("/{event_id}/lock", response_model=Event)
async def lock_event(
    event_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    existing = await repo.get_event(event_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")
    result = await repo.lock_event(event_id, current_user)
    if not result:
        logger.warning("Lock attempt on already-locked event %s", event_id)
        raise HTTPException(status_code=423, detail="Event is already locked")
    return result


@router.post("/{event_id}/unlock", response_model=Event)
async def unlock_event(
    event_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    existing = await repo.get_event(event_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")
    result = await repo.unlock_event(event_id, current_user)
    if not result:
        logger.warning("Unlock attempt failed for event %s — not locked by caller", event_id)
        raise HTTPException(status_code=403, detail="Event is locked by another user")
    return result
