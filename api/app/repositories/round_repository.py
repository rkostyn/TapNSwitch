import uuid
from datetime import UTC, datetime

from pymongo import ReturnDocument

from app.db.mongo import DB_NAME, MongoClient
from app.logger import get_logger
from app.models.round import Round, RoundCreate

logger = get_logger(__name__)


class RoundRepository:
    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client

    async def _collection(self):
        return await self.mongo_client.get_collection(DB_NAME, "rounds")

    async def create_round(self, round_create: RoundCreate) -> Round:
        collection = await self._collection()
        round_id = str(uuid.uuid4())
        doc = {
            "round_id": round_id,
            "match_id": round_create.match_id,
            "player_1_id": round_create.player_1_id,
            "player_2_id": round_create.player_2_id,
            "sequence": round_create.sequence,
            "timestamp": datetime.now(UTC),
            "is_locked": False,
            "locked_by": None,
            "locked_at": None,
        }
        await collection.insert_one(doc)
        logger.info("Round created: %s (match=%s seq=%d)", round_id, round_create.match_id, round_create.sequence)
        return Round(**doc)

    async def get_round(self, round_id: str) -> Round | None:
        collection = await self._collection()
        doc = await collection.find_one({"round_id": round_id}, {"_id": 0})
        if not doc:
            logger.warning("Round not found: %s", round_id)
            return None
        return Round(**doc)

    async def get_rounds_by_match(self, match_id: str) -> list[Round]:
        collection = await self._collection()
        cursor = collection.find({"match_id": match_id}, {"_id": 0}).sort("sequence", 1)
        return [Round(**doc) async for doc in cursor]

    async def lock_round(self, round_id: str, user_id: str) -> Round | None:
        collection = await self._collection()
        doc = await collection.find_one_and_update(
            {"round_id": round_id, "is_locked": False},
            {"$set": {"is_locked": True, "locked_by": user_id, "locked_at": datetime.now(UTC)}},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        if doc:
            logger.info("Round locked: %s", round_id)
        return Round(**doc) if doc else None

    async def delete_round(self, round_id: str) -> bool:
        collection = await self._collection()
        result = await collection.delete_one({"round_id": round_id})
        if result.deleted_count == 1:
            logger.info("Round deleted: %s", round_id)
            return True
        logger.warning("Delete matched no documents for round_id: %s", round_id)
        return False

    async def delete_rounds_by_match_ids(self, match_ids: list[str]) -> int:
        if not match_ids:
            return 0
        collection = await self._collection()
        result = await collection.delete_many({"match_id": {"$in": match_ids}})
        logger.info("Deleted %d rounds for %d match(es)", result.deleted_count, len(match_ids))
        return result.deleted_count

    async def unlock_round(self, round_id: str, user_id: str) -> Round | None:
        collection = await self._collection()
        doc = await collection.find_one_and_update(
            {"round_id": round_id, "is_locked": True, "locked_by": user_id},
            {"$set": {"is_locked": False, "locked_by": None, "locked_at": None}},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        if doc:
            logger.info("Round unlocked: %s", round_id)
        return Round(**doc) if doc else None
