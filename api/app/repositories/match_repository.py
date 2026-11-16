from datetime import UTC, datetime

from pymongo import ReturnDocument

from app.db.mongo import DB_NAME, MongoClient
from app.logger import get_logger
from app.models.match import Match, MatchCreate
from app.repositories.documents import new_match_document

logger = get_logger(__name__)


class MatchRepository:
    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client

    async def _collection(self):
        return await self.mongo_client.get_collection(DB_NAME, "matches")

    async def create_match(self, match_create: MatchCreate) -> Match:
        collection = await self._collection()
        doc = new_match_document(
            event_id=match_create.event_id,
            player_1_id=match_create.player_1_id,
            player_2_id=match_create.player_2_id,
            sequence=match_create.sequence,
            match_type=match_create.match_type,
            rounds_per_match=match_create.rounds_per_match,
        )
        await collection.insert_one(doc)
        logger.info("Match created: %s (event=%s seq=%d)", doc["match_id"], match_create.event_id, match_create.sequence)
        return Match(**doc)

    async def get_match(self, match_id: str) -> Match | None:
        collection = await self._collection()
        doc = await collection.find_one({"match_id": match_id}, {"_id": 0})
        if not doc:
            logger.warning("Match not found: %s", match_id)
            return None
        return Match(**doc)

    async def get_matches_by_event(self, event_id: str, match_type: str | None = None) -> list[Match]:
        collection = await self._collection()
        query: dict = {"event_id": event_id}
        if match_type:
            query["match_type"] = match_type
        cursor = collection.find(query, {"_id": 0}).sort("sequence", 1)
        return [Match(**doc) async for doc in cursor]

    async def get_match_ids_by_event(self, event_id: str) -> list[str]:
        collection = await self._collection()
        cursor = collection.find({"event_id": event_id}, {"_id": 0, "match_id": 1})
        return [doc["match_id"] async for doc in cursor]

    async def insert_matches(self, docs: list[dict]) -> list[Match]:
        collection = await self._collection()
        await collection.insert_many(docs)
        logger.info("Inserted %d matches", len(docs))
        return [Match(**doc) for doc in docs]

    async def lock_match(self, match_id: str, user_id: str) -> Match | None:
        collection = await self._collection()
        doc = await collection.find_one_and_update(
            {"match_id": match_id, "is_locked": False},
            {"$set": {"is_locked": True, "locked_by": user_id, "locked_at": datetime.now(UTC)}},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        if doc:
            logger.info("Match locked: %s", match_id)
        return Match(**doc) if doc else None

    async def finish_match(self, match_id: str) -> Match | None:
        collection = await self._collection()
        doc = await collection.find_one_and_update(
            {"match_id": match_id, "is_finished": False},
            {"$set": {"is_finished": True, "finished_at": datetime.now(UTC)}},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        if doc:
            logger.info("Match finished: %s", match_id)
        return Match(**doc) if doc else None

    async def delete_match(self, match_id: str) -> bool:
        collection = await self._collection()
        result = await collection.delete_one({"match_id": match_id})
        if result.deleted_count == 1:
            logger.info("Match deleted: %s", match_id)
            return True
        logger.warning("Delete matched no documents for match_id: %s", match_id)
        return False

    async def delete_matches(self, match_ids: list[str]) -> int:
        if not match_ids:
            return 0
        collection = await self._collection()
        result = await collection.delete_many({"match_id": {"$in": list(match_ids)}})
        logger.info("Deleted %d matches by id", result.deleted_count)
        return result.deleted_count

    async def event_has_matches(self, event_id: str) -> bool:
        collection = await self._collection()
        return await collection.find_one({"event_id": event_id}, {"_id": 0, "match_id": 1}) is not None

    async def delete_matches_by_event(self, event_id: str, match_type: str | None = None) -> int:
        collection = await self._collection()
        query: dict = {"event_id": event_id}
        if match_type:
            query["match_type"] = match_type
        result = await collection.delete_many(query)
        logger.info("Deleted %d matches for event %s (type=%s)", result.deleted_count, event_id, match_type)
        return result.deleted_count

    async def force_lock_match(self, match_id: str, user_id: str) -> Match | None:
        collection = await self._collection()
        doc = await collection.find_one_and_update(
            {"match_id": match_id},
            {"$set": {"is_locked": True, "locked_by": user_id, "locked_at": datetime.now(UTC)}},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        if doc:
            logger.info("Match lock taken over: %s by %s", match_id, user_id)
        return Match(**doc) if doc else None

    async def reopen_match(self, match_id: str) -> Match | None:
        collection = await self._collection()
        doc = await collection.find_one_and_update(
            {"match_id": match_id, "is_finished": True},
            {"$set": {"is_finished": False, "finished_at": None, "winner_id": None}},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        if doc:
            logger.info("Match reopened: %s", match_id)
        return Match(**doc) if doc else None

    async def update_rounds_per_match(self, match_id: str, rounds_per_match: int) -> Match | None:
        collection = await self._collection()
        doc = await collection.find_one_and_update(
            {"match_id": match_id},
            {"$set": {"rounds_per_match": rounds_per_match}},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        if doc:
            logger.info("Match %s rounds_per_match set to %d", match_id, rounds_per_match)
        return Match(**doc) if doc else None

    async def set_winner(self, match_id: str, winner_id: str | None) -> Match | None:
        collection = await self._collection()
        doc = await collection.find_one_and_update(
            {"match_id": match_id},
            {"$set": {"winner_id": winner_id}},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        return Match(**doc) if doc else None

    async def get_bracket_match(self, event_id: str, bracket_round: int, bracket_slot: int) -> Match | None:
        collection = await self._collection()
        doc = await collection.find_one(
            {"event_id": event_id, "match_type": "bracket", "bracket_round": bracket_round, "bracket_slot": bracket_slot},
            {"_id": 0},
        )
        return Match(**doc) if doc else None

    async def set_bracket_player(self, match_id: str, position: int, player_id: str) -> Match | None:
        field = "player_1_id" if position == 0 else "player_2_id"
        collection = await self._collection()
        doc = await collection.find_one_and_update(
            {"match_id": match_id},
            {"$set": {field: player_id}},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        if doc:
            logger.info("Bracket match %s %s set to %s", match_id, field, player_id)
        return Match(**doc) if doc else None

    async def unlock_match(self, match_id: str, user_id: str) -> Match | None:
        collection = await self._collection()
        doc = await collection.find_one_and_update(
            {"match_id": match_id, "is_locked": True, "locked_by": user_id},
            {"$set": {"is_locked": False, "locked_by": None, "locked_at": None}},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        if doc:
            logger.info("Match unlocked: %s", match_id)
        return Match(**doc) if doc else None
