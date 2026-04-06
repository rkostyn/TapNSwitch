"""
Unit tests for the MongoClient wrapper (app/db/mongo.py).
The underlying AsyncMongoClient is mocked so no real connection is needed.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.mongo import MongoClient


def _make_mock_motor():
    """Return a MagicMock that stands in for AsyncMongoClient."""
    motor = MagicMock()
    motor.admin.command = AsyncMock(return_value={"ok": 1})
    motor.close = AsyncMock()
    return motor


@pytest.fixture
def mongo_wrapper():
    with patch("app.db.mongo.AsyncMongoClient") as mock_cls:
        mock_motor = _make_mock_motor()
        mock_cls.return_value = mock_motor
        client = MongoClient()
        client._motor = mock_motor  # expose for assertions
        yield client


async def test_ping_success(mongo_wrapper):
    result = await mongo_wrapper.ping()
    assert result is True
    mongo_wrapper._motor.admin.command.assert_awaited_once_with("ping")


async def test_ping_failure(mongo_wrapper):
    mongo_wrapper._motor.admin.command.side_effect = Exception("connection refused")
    result = await mongo_wrapper.ping()
    assert result is False


async def test_get_database_returns_correct_name(mongo_wrapper):
    fake_db = MagicMock()
    fake_db.name = "test_db"
    mongo_wrapper._motor.__getitem__ = MagicMock(return_value=fake_db)
    db = await mongo_wrapper.get_database("test_db")
    assert db.name == "test_db"


async def test_get_collection_returns_collection(mongo_wrapper):
    fake_col = MagicMock()
    fake_col.name = "test_collection"
    fake_db = MagicMock()
    fake_db.__getitem__ = MagicMock(return_value=fake_col)
    mongo_wrapper._motor.__getitem__ = MagicMock(return_value=fake_db)
    col = await mongo_wrapper.get_collection("test_db", "test_collection")
    assert col.name == "test_collection"


async def test_close_calls_motor_close(mongo_wrapper):
    mongo_wrapper._motor.close = AsyncMock()
    await mongo_wrapper.close()
    mongo_wrapper._motor.close.assert_awaited_once()


async def test_drop_database_delegates(mongo_wrapper):
    mongo_wrapper._motor.drop_database = AsyncMock()
    await mongo_wrapper.drop_database("test_db")
    mongo_wrapper._motor.drop_database.assert_awaited_once_with("test_db")


async def test_drop_collection_delegates(mongo_wrapper):
    fake_db = MagicMock()
    fake_db.drop_collection = AsyncMock()
    mongo_wrapper._motor.__getitem__ = MagicMock(return_value=fake_db)
    await mongo_wrapper.drop_collection("test_db", "test_collection")
    fake_db.drop_collection.assert_awaited_once_with("test_collection")


async def test_create_index_delegates(mongo_wrapper):
    fake_col = MagicMock()
    fake_col.create_index = AsyncMock()
    fake_db = MagicMock()
    fake_db.__getitem__ = MagicMock(return_value=fake_col)
    mongo_wrapper._motor.__getitem__ = MagicMock(return_value=fake_db)
    await mongo_wrapper.create_index("test_db", "test_collection", [("field", 1)], unique=True)
    fake_col.create_index.assert_awaited_once_with([("field", 1)], unique=True)
