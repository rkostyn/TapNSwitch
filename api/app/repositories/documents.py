"""The one place each stored document shape is written down.

Every new event and match document is built here, so the manual, Checkfront,
swiss and bracket paths cannot drift apart. These are plain functions with no
database access; callers insert the result.
"""
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from app.models.event import EventType, default_pairing_style

_UNSET = object()


def new_event_document(
    *,
    event_name: str,
    players: list[str],
    created_by: str,
    start_timestamp: datetime | None,
    swiss_matches_per_player: int,
    swiss_rounds_per_match: int,
    suggested_arena_count: int,
    suggested_arena_ids: Iterable[str] = (),
    event_type: EventType = "standard",
    checkfront: dict | None = None,
    now: datetime | None = None,
) -> dict:
    """A new event. ``checkfront`` holds the ``checkfront_*`` fields for an
    imported booking; its presence makes the event's source ``checkfront``.
    The pairing style starts as the event type's default."""
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "event_name": event_name,
        "players": list(players),
        "late_players": [],
        "created_by": created_by,
        "source": "checkfront" if checkfront is not None else "manual",
        **(checkfront or {}),
        "suggested_arena_count": suggested_arena_count,
        "suggested_arena_ids": list(suggested_arena_ids),
        "arena_ids": [],
        "start_timestamp": start_timestamp,
        "timestamp": now or datetime.now(UTC),
        "pairing_style": default_pairing_style(event_type),
        "swiss_matches_per_player": swiss_matches_per_player,
        "swiss_rounds_per_match": swiss_rounds_per_match,
        "swiss_generated_at": None,
        "swiss_standings": None,
        "standings_generated_at": None,
        "bracket_rounds_per_match": 3,
        "bracket_generated_at": None,
        "is_locked": False,
        "locked_by": None,
        "locked_at": None,
        "is_finished": False,
        "finished_at": None,
    }


def new_match_document(
    *,
    event_id: str | None,
    player_1_id: str | None,
    player_2_id: str | None,
    sequence: int,
    match_type: str,
    rounds_per_match: int,
    bracket_round: int | None = None,
    bracket_slot: int | None = None,
    arena_id=_UNSET,
    now: datetime | None = None,
) -> dict:
    """A new, unplayed match. ``arena_id`` is only stored when passed (swiss
    matches dealt onto lanes); other matches have no such key."""
    doc = {
        "match_id": str(uuid.uuid4()),
        "event_id": event_id,
        "player_1_id": player_1_id,
        "player_2_id": player_2_id,
        "sequence": sequence,
        "match_type": match_type,
        "rounds_per_match": rounds_per_match,
        "bracket_round": bracket_round,
        "bracket_slot": bracket_slot,
        "winner_id": None,
        "timestamp": now or datetime.now(UTC),
        "is_locked": False,
        "locked_by": None,
        "locked_at": None,
        "is_finished": False,
        "finished_at": None,
    }
    if arena_id is not _UNSET:
        doc["arena_id"] = arena_id
    return doc
