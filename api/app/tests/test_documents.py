"""Every path that creates events and matches writes the same document shape."""
from datetime import UTC, datetime

from app.db.mongo import DB_NAME
from app.models.event import EventCreate
from app.models.match import MatchCreate
from app.repositories.event_repository import EventRepository
from app.repositories.match_repository import MatchRepository
from app.services.event_stages import swiss_match_docs
from app.services.tournament import build_bracket_matches
from app.tests.fakes import FakeMongoClient

_MATCH_KEYS = {
    "match_id", "event_id", "player_1_id", "player_2_id", "sequence", "match_type",
    "rounds_per_match", "bracket_round", "bracket_slot", "winner_id", "timestamp",
    "is_locked", "locked_by", "locked_at", "is_finished", "finished_at",
}

_EVENT_KEYS = {
    "event_id", "event_type", "event_name", "players", "late_players", "created_by", "source",
    "suggested_arena_count", "suggested_arena_ids", "arena_ids", "start_timestamp",
    "timestamp", "pairing_style", "swiss_matches_per_player", "swiss_rounds_per_match",
    "swiss_generated_at", "swiss_standings", "standings_generated_at",
    "bracket_rounds_per_match", "bracket_generated_at", "is_locked", "locked_by",
    "locked_at", "is_finished", "finished_at",
}

_CHECKFRONT_KEYS = {
    "checkfront_booking_id", "checkfront_booking_code", "checkfront_session_key",
    "checkfront_booking_ids", "checkfront_item_skus", "checkfront_qty",
}


async def _stored(mongo, collection):
    return (await mongo.get_collection(DB_NAME, collection))._docs


async def test_match_shapes_agree():
    mongo = FakeMongoClient()
    await MatchRepository(mongo).create_match(
        MatchCreate(event_id="e", player_1_id="a", player_2_id="b", sequence=1)
    )
    (created,) = await _stored(mongo, "matches")
    now = datetime.now(UTC)
    swiss = swiss_match_docs("e", [("a", "b"), ("c", "d")], 2, now)
    dealt = swiss_match_docs("e", [("a", "b"), ("c", "d")], 2, now, lane_ids=["red-1"])
    bracket = build_bracket_matches(["a", "b", "c"], "e", 3)

    assert set(created) == _MATCH_KEYS
    assert all(set(d) == _MATCH_KEYS for d in swiss + bracket)
    assert all(set(d) == _MATCH_KEYS | {"arena_id"} for d in dealt)
    assert [d["arena_id"] for d in dealt] == ["red-1", "red-1"]
    assert [d["sequence"] for d in swiss] == [1, 2]
    assert len({d["match_id"] for d in swiss + bracket}) == len(swiss + bracket)


async def test_event_shapes_agree():
    mongo = FakeMongoClient()
    repo = EventRepository(mongo)
    body = EventCreate(event_name="Group", players=["a", "b"])
    await repo.create_event(body, "coach")
    await repo.create_checkfront_event(body, booking_id="B1", booking_code="CODE", session_key=None, qty=8)
    manual, imported = await _stored(mongo, "events")

    assert set(manual) == _EVENT_KEYS
    assert manual["source"] == "manual" and manual["created_by"] == "coach"
    assert set(imported) == _EVENT_KEYS | _CHECKFRONT_KEYS
    assert imported["source"] == "checkfront" and imported["created_by"] == "checkfront"
    assert imported["checkfront_booking_ids"] == ["B1"]
    assert imported["suggested_arena_count"] == 2  # sized by qty=8, not the 2 names
    assert manual["event_type"] == imported["event_type"] == "standard"
