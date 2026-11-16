"""Tests that the in-memory fake Mongo matches documents like real MongoDB."""
from datetime import datetime

import pytest
from pymongo import ReturnDocument

from app.tests.fakes import (
    FakeCollection,
    FakeWriteError,
    UnsupportedQueryOperator,
    _apply_update,
    _matches_filter,
)


def test_none_matches_missing_and_null():
    assert _matches_filter({}, {"a": None})
    assert _matches_filter({"a": None}, {"a": None})
    assert not _matches_filter({"a": 1}, {"a": None})


def test_exists():
    assert _matches_filter({"a": None}, {"a": {"$exists": True}})
    assert not _matches_filter({}, {"a": {"$exists": True}})
    assert _matches_filter({}, {"a": {"$exists": False}})


def test_range_and_missing_field():
    lo, mid, hi = datetime(2026, 1, 1), datetime(2026, 1, 2), datetime(2026, 1, 3)
    assert _matches_filter({"t": mid}, {"t": {"$gte": lo, "$lte": hi}})
    assert not _matches_filter({"t": hi}, {"t": {"$gte": lo, "$lt": hi}})
    assert not _matches_filter({}, {"t": {"$gte": lo}})
    assert not _matches_filter({"t": None}, {"t": {"$gte": lo}})


def test_regex_with_options_and_arrays():
    cond = {"$regex": "ali", "$options": "i"}
    assert _matches_filter({"name": "ALICE"}, {"name": cond})
    assert _matches_filter({"players": ["Bob", "Alice"]}, {"players": cond})
    assert not _matches_filter({"players": ["Bob"]}, {"players": cond})
    assert not _matches_filter({"players": [1, 2]}, {"players": cond})


def test_scalar_equality_and_in_on_arrays():
    assert _matches_filter({"tags": ["a", "b"]}, {"tags": "b"})
    assert _matches_filter({"tags": ["a", "b"]}, {"tags": ["a", "b"]})
    assert _matches_filter({"tags": ["a", "b"]}, {"tags": {"$in": ["z", "a"]}})
    assert not _matches_filter({"tags": ["a"]}, {"tags": {"$in": ["z"]}})
    assert _matches_filter({}, {"tags": {"$in": [None]}})


def test_logical_operators():
    doc = {"a": 1, "b": 2}
    assert _matches_filter(doc, {"$and": [{"a": 1}, {"$or": [{"b": 3}, {"b": 2}]}]})
    assert not _matches_filter(doc, {"$and": [{"a": 1}, {"b": 3}]})
    assert _matches_filter(doc, {"$nor": [{"a": 2}]})


def test_unknown_operator_raises():
    with pytest.raises(UnsupportedQueryOperator):
        _matches_filter({"a": 1}, {"a": {"$elemMatch": {"x": 1}}})
    with pytest.raises(UnsupportedQueryOperator):
        _matches_filter({"a": 1}, {"$where": "true"})


# ---------------------------------------------------------------------------
# $size and update operators
# ---------------------------------------------------------------------------

def test_size():
    assert _matches_filter({"a": [1, 2]}, {"a": {"$size": 2}})
    assert not _matches_filter({"a": [1, 2]}, {"a": {"$size": 1}})
    assert not _matches_filter({}, {"a": {"$size": 0}})
    assert not _matches_filter({"a": "xy"}, {"a": {"$size": 2}})
    # Combined with an element condition on the same field
    assert _matches_filter({"a": ["x", "y"]}, {"a": {"$ne": "z", "$size": 2}})
    assert not _matches_filter({"a": ["x", "y"]}, {"a": {"$ne": "x", "$size": 2}})
    assert _matches_filter({"a": ["x", "y"]}, {"a": {"$eq": "x", "$size": 2}})


def test_add_to_set():
    doc = {"a": ["x"]}
    _apply_update(doc, {"$addToSet": {"a": "x", "b": "y"}})
    assert doc == {"a": ["x"], "b": ["y"]}
    _apply_update(doc, {"$addToSet": {"a": {"$each": ["x", "z", "z"]}}})
    assert doc["a"] == ["x", "z"]


def test_push_keeps_duplicates():
    doc = {"a": ["x"]}
    _apply_update(doc, {"$push": {"a": "x"}})
    _apply_update(doc, {"$push": {"a": {"$each": ["y", "z"]}}})
    assert doc["a"] == ["x", "x", "y", "z"]


def test_pull():
    doc = {"a": ["x", "y", "x"], "n": [1, 5, 9]}
    _apply_update(doc, {"$pull": {"a": "x", "missing": "x", "n": {"$gte": 5}}})
    assert doc == {"a": ["y"], "n": [1]}


def test_update_on_non_array_fails_without_partial_write():
    doc = {"a": "scalar", "b": 1}
    with pytest.raises(FakeWriteError):
        _apply_update(doc, {"$set": {"b": 2}, "$push": {"a": "x"}})
    assert doc == {"a": "scalar", "b": 1}


def test_conflicting_paths_rejected():
    with pytest.raises(FakeWriteError):
        _apply_update({"a": []}, {"$set": {"a": []}, "$pull": {"a": "x"}})


def test_unknown_update_operator_raises():
    with pytest.raises(UnsupportedQueryOperator):
        _apply_update({"a": 1}, {"$inc": {"a": 1}})


async def test_find_one_and_update_return_document():
    coll = FakeCollection()
    await coll.insert_one({"k": 1, "v": 0})
    before = await coll.find_one_and_update({"k": 1}, {"$set": {"v": 1}})
    after = await coll.find_one_and_update({"k": 1}, {"$set": {"v": 2}}, return_document=ReturnDocument.AFTER)
    assert before["v"] == 0
    assert after["v"] == 2
