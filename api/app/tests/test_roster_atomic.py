"""Roster edits and arena assignment stay correct when devices race.

The fakes run each await to completion, so races are simulated by handing the
repository a stale read: the write must then notice the roster changed.
"""
import asyncio

import pytest

from app.models.event import EventCreate
from app.repositories.event_repository import EventRepository, RosterConflictError
from app.services.errors import ConflictError
from app.services.lanes import ARENA_LOCK_KEY, ArenaOccupiedError, assign_event_arenas
from app.tests.fakes import FakeMongoClient, FakeRedisClient


@pytest.fixture
def repo():
    return EventRepository(FakeMongoClient())


async def _event(repo, players):
    return await repo.create_event(EventCreate(event_name="Group", players=players), "coach")


def _stale_reads(monkeypatch, repo, snapshot, times=1):
    """Make the next ``times`` get_event calls return ``snapshot``."""
    real = repo.get_event
    calls = {"n": 0}

    async def get_event(event_id):
        calls["n"] += 1
        if calls["n"] <= times:
            return snapshot
        return await real(event_id)

    monkeypatch.setattr(repo, "get_event", get_event)
    return calls


async def test_concurrent_adds_keep_both_players_and_the_count(repo, monkeypatch):
    names = [f"p{i}" for i in range(6)]
    event = await _event(repo, names)
    stale = event.model_copy(deep=True)
    # Another iPad adds p6 after our read of the 6-player roster.
    await repo.add_player(event.event_id, "p6")
    calls = _stale_reads(monkeypatch, repo, stale)

    result = await repo.add_player(event.event_id, "p7")

    assert result.players == names + ["p6", "p7"]
    assert result.suggested_arena_count == 2  # 8 players, not the stale 7
    assert calls["n"] == 2  # first write refused, re-read, retried


async def test_add_detects_player_added_concurrently(repo, monkeypatch):
    event = await _event(repo, ["a", "b"])
    stale = event.model_copy(deep=True)
    await repo.add_player(event.event_id, "c")
    _stale_reads(monkeypatch, repo, stale)

    with pytest.raises(ValueError, match="already in the event"):
        await repo.add_player(event.event_id, "c")
    assert (await repo.get_event(event.event_id)).players == ["a", "b", "c"]


async def test_remove_detects_player_removed_concurrently(repo, monkeypatch):
    event = await _event(repo, ["a", "b", "c"])
    stale = event.model_copy(deep=True)
    await repo.remove_player(event.event_id, "c")
    _stale_reads(monkeypatch, repo, stale)

    with pytest.raises(ValueError, match="not in the event"):
        await repo.remove_player(event.event_id, "c")


async def test_remove_racing_an_add_keeps_the_add_and_the_count(repo, monkeypatch):
    names = [f"p{i}" for i in range(7)]
    event = await _event(repo, names)
    assert event.suggested_arena_count == 2
    stale = event.model_copy(deep=True)
    await repo.add_player(event.event_id, "p7")
    _stale_reads(monkeypatch, repo, stale)

    result = await repo.remove_player(event.event_id, "p0")

    assert result.players == names[1:] + ["p7"]
    assert result.suggested_arena_count == 2  # 7 players


async def test_remove_clears_late_flag_and_count(repo):
    event = await _event(repo, [f"p{i}" for i in range(7)])
    await repo.set_player_late(event.event_id, "p3", True)
    result = await repo.remove_player(event.event_id, "p3")
    assert "p3" not in result.players
    assert result.late_players == []
    assert result.suggested_arena_count == 1


async def test_persistent_contention_gives_up_with_conflict(repo, monkeypatch):
    event = await _event(repo, ["a", "b"])
    stale = event.model_copy(update={"players": ["a"]})  # size never matches
    _stale_reads(monkeypatch, repo, stale, times=100)
    with pytest.raises(RosterConflictError):
        await repo.add_player(event.event_id, "z")
    assert isinstance(RosterConflictError("x"), ConflictError)


async def test_set_late_is_conditional_on_membership(repo):
    event = await _event(repo, ["a", "b"])
    result = await repo.set_player_late(event.event_id, "a", True)
    assert result.late_players == ["a"]
    result = await repo.set_player_late(event.event_id, "a", True)
    assert result.late_players == ["a"]  # idempotent
    result = await repo.set_player_late(event.event_id, "a", False)
    assert result.late_players == []
    with pytest.raises(ValueError, match="not in the event"):
        await repo.set_player_late(event.event_id, "zed", True)
    assert await repo.set_player_late("missing", "a", True) is None


async def test_roster_methods_return_none_for_missing_event(repo):
    assert await repo.add_player("missing", "a") is None
    assert await repo.remove_player("missing", "a") is None


def test_roster_routes_keep_their_errors(client, auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    event_id = client.post("/event", json={"event_name": "R", "players": ["a", "b"]}, headers=headers).json()["event_id"]
    assert client.post(f"/event/{event_id}/player", json={"player_name": "a"}, headers=headers).status_code == 409
    assert client.delete(f"/event/{event_id}/player/zed", headers=headers).status_code == 404
    response = client.put(f"/event/{event_id}/player/zed/late", json={"late": True}, headers=headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "Player is not in the event"}


# ---------------------------------------------------------------------------
# Arena assignment
# ---------------------------------------------------------------------------

async def test_arena_assignments_are_serialised(repo, monkeypatch):
    redis = FakeRedisClient()
    first = await _event(repo, ["a"])
    second = await _event(repo, ["b"])
    real = repo.get_open_events

    async def slow_open_events():
        # Yield between the clash check's read and its write so that, without
        # the lock, both assignments would read an empty floor.
        events = await real()
        await asyncio.sleep(0.01)
        return events

    monkeypatch.setattr(repo, "get_open_events", slow_open_events)
    results = await asyncio.gather(
        assign_event_arenas(repo, redis, first, ["red"]),
        assign_event_arenas(repo, redis, second, ["red"]),
        return_exceptions=True,
    )
    assert sum(isinstance(r, ArenaOccupiedError) for r in results) == 1
    assert await redis.acquire_lock(ARENA_LOCK_KEY, 1) is not None  # released


async def test_arena_assignment_waits_then_gives_up_when_lock_is_held(repo, monkeypatch):
    monkeypatch.setattr("app.services.lanes.ARENA_LOCK_WAIT_SECONDS", 0.1)
    redis = FakeRedisClient()
    event = await _event(repo, ["a"])
    assert await redis.acquire_lock(ARENA_LOCK_KEY, 30)
    with pytest.raises(ConflictError, match="in progress"):
        await assign_event_arenas(repo, redis, event, ["blue"])
    assert (await repo.get_event(event.event_id)).arena_ids == []


async def test_arena_lock_released_on_clash(repo):
    redis = FakeRedisClient()
    first = await _event(repo, ["a"])
    second = await _event(repo, ["b"])
    await assign_event_arenas(repo, redis, first, ["red"])
    with pytest.raises(ArenaOccupiedError):
        await assign_event_arenas(repo, redis, second, ["red"])
    assert (await assign_event_arenas(repo, redis, second, ["blue"])).arena_ids == ["blue"]


# ---------------------------------------------------------------------------
# Event type switch racing swiss generation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generation_rolls_back_if_type_switched_mid_flight(monkeypatch):
    from app.repositories.match_repository import MatchRepository
    from app.services import event_stages

    mongo = FakeMongoClient()
    repo = EventRepository(mongo)
    event = await _event(repo, ["A", "B", "C", "D"])
    real_insert = MatchRepository.insert_matches

    async def insert_then_switch(self, docs):
        inserted = await real_insert(self, docs)
        # Another iPad switches the type after our read, before we mark done.
        await repo.update_event_fields(event.event_id, {"event_type": "tournament"})
        return inserted

    monkeypatch.setattr(MatchRepository, "insert_matches", insert_then_switch)
    with pytest.raises(ConflictError):
        await event_stages.generate_swiss_matches(mongo, event.event_id)
    assert await MatchRepository(mongo).get_matches_by_event(event.event_id) == []
    assert (await repo.get_event(event.event_id)).swiss_generated_at is None


@pytest.mark.asyncio
async def test_type_switch_loses_to_generation_that_lands_first(monkeypatch):
    from datetime import UTC, datetime

    from app.repositories.match_repository import MatchRepository
    from app.services import event_stages

    mongo = FakeMongoClient()
    repo = EventRepository(mongo)
    event = await _event(repo, ["A", "B"])

    async def no_matches_yet_then_generated(self, event_id):
        # Generation completes between the switch's match check and its write.
        await repo.update_event_fields(event_id, {"swiss_generated_at": datetime.now(UTC)})
        return False

    monkeypatch.setattr(MatchRepository, "event_has_matches", no_matches_yet_then_generated)
    with pytest.raises(ConflictError):
        await event_stages.set_event_type(mongo, event.event_id, "tournament")
    stored = await repo.get_event(event.event_id)
    assert (stored.event_type, stored.pairing_style) == ("standard", "round_robin")
