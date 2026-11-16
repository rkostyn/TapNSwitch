import uuid
from datetime import UTC, datetime

from app.db.mongo import DB_NAME, MongoClient
from app.logger import get_logger
from app.models.throw import Throw, ThrowGet, ThrowsGet, ThrowSubmit

logger = get_logger(__name__)


class ThrowRepository:
    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client

    async def _collection(self):
        return await self.mongo_client.get_collection(DB_NAME, "throws")

    async def submit_throw(self, throw_submit: ThrowSubmit) -> dict:
        collection = await self._collection()
        data = throw_submit.model_dump()
        data["throw_id"] = str(uuid.uuid4())
        if data["timestamp"] is None:
            data["timestamp"] = datetime.now(UTC)
        await collection.insert_one(data)
        logger.info("Throw submitted: %s (player=%s)", data["throw_id"], throw_submit.player_id)
        return {"throw_id": data["throw_id"]}

    async def get_throw_by_id(self, throw_get: ThrowGet) -> Throw | None:
        collection = await self._collection()
        doc = await collection.find_one({"throw_id": throw_get.throw_id}, {"_id": 0})
        if not doc:
            logger.warning("Throw not found: %s", throw_get.throw_id)
            return None
        logger.info("Throw found: %s", throw_get.throw_id)
        return Throw(**doc)

    async def delete_throw(self, throw_id: str) -> bool:
        collection = await self._collection()
        result = await collection.delete_one({"throw_id": throw_id})
        if result.deleted_count == 1:
            logger.info("Throw deleted: %s", throw_id)
            return True
        logger.warning("Delete matched no documents for throw_id: %s", throw_id)
        return False

    async def delete_throws_by_match_ids(self, match_ids: list[str]) -> int:
        if not match_ids:
            return 0
        collection = await self._collection()
        result = await collection.delete_many({"match_id": {"$in": match_ids}})
        logger.info("Deleted %d throws for %d match(es)", result.deleted_count, len(match_ids))
        return result.deleted_count

    async def delete_throws_by_event(self, event_id: str) -> int:
        collection = await self._collection()
        result = await collection.delete_many({"event_id": event_id})
        logger.info("Deleted %d throws for event %s", result.deleted_count, event_id)
        return result.deleted_count

    async def get_throws_by_criteria(self, throws_get: ThrowsGet) -> list[Throw]:
        collection = await self._collection()
        query = throws_get.model_dump(exclude_none=True)
        logger.info("Searching throws with %d filter(s)", len(query))
        results = [Throw(**doc) async for doc in collection.find(query, {"_id": 0})]
        logger.info("Throw search returned %d result(s)", len(results))
        return results
