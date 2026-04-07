"""
Unit tests for ThrowRepository against the in-memory FakeMongoClient.
"""
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from app.models.throw import ThrowGet, ThrowSubmit, ThrowsGet
from app.repositories.throw_repository import ThrowRepository
from app.tests.fakes import FakeMongoClient, FakeRedisClient

throw_submit = ThrowSubmit(
    timestamp=datetime.now(UTC),
    player_id="test_player",
    round_id="test_round",
    match_id="test_match",
    event_id="test_event",
    venue_id="test_venue",
    points=10,
    clutch_called=True,
    is_premier=False,
    is_drop=False,
)


@pytest.fixture
def fake_mongo():
    return FakeMongoClient()


@pytest.fixture
def repo(fake_mongo):
    # ThrowRepository creates a RedisClient internally; patch it out
    with patch("app.repositories.throw_repository.RedisClient", return_value=FakeRedisClient()):
        return ThrowRepository(fake_mongo)


async def test_throw_submit(repo):
    result = await repo.submit_throw(throw_submit)
    assert result["throw_id"]


async def test_get_throw_by_id(repo):
    result = await repo.submit_throw(throw_submit)
    throw_id = result["throw_id"]
    found = await repo.get_throw_by_id(ThrowGet(throw_id=throw_id))
    assert found is not None
    assert found.throw_id == throw_id


async def test_get_throw_by_id_not_found(repo):
    result = await repo.get_throw_by_id(ThrowGet(throw_id="nonexistent-id"))
    assert result is None


async def test_get_throws_by_criteria(repo):
    player_id = "criteria_test_player"
    custom = throw_submit.model_copy(update={"player_id": player_id})
    await repo.submit_throw(custom)

    results = await repo.get_throws_by_criteria(ThrowsGet(player_id=player_id))
    assert len(results) >= 1
    assert all(t.player_id == player_id for t in results)


async def test_get_throws_by_criteria_no_match(repo):
    results = await repo.get_throws_by_criteria(ThrowsGet(player_id="nonexistent_player_xyz"))
    assert results == []


async def test_delete_throw(repo):
    result = await repo.submit_throw(throw_submit)
    throw_id = result["throw_id"]
    assert await repo.delete_throw(throw_id) is True
    assert await repo.get_throw_by_id(ThrowGet(throw_id=throw_id)) is None


async def test_delete_throw_not_found(repo):
    assert await repo.delete_throw("does-not-exist") is False
