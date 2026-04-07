import uuid
from datetime import UTC, datetime
from pymongo import ReturnDocument
from app.db.mongo import MongoClient
from app.models.event import Event, EventCreate
from app.logger import get_logger

logger = get_logger(__name__)


class EventRepository:
    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client

    async def _collection(self):
        return await self.mongo_client.get_collection("axes", "events")

    async def create_event(self, event_create: EventCreate) -> Event:
        collection = await self._collection()
        event_id = str(uuid.uuid4())
        doc = {
            "event_id": event_id,
            "venue_id": event_create.venue_id,
            "start_timestamp": event_create.start_timestamp,
            "timestamp": datetime.now(UTC),
            "is_locked": False,
            "locked_by": None,
            "locked_at": None,
            "is_finished": False,
            "finished_at": None,
        }
        await collection.insert_one(doc)
        logger.info("Event created: %s (venue=%s)", event_id, event_create.venue_id)
        return Event(**doc)

    async def get_event(self, event_id: str) -> Event | None:
        collection = await self._collection()
        doc = await collection.find_one({"event_id": event_id}, {"_id": 0})
        if not doc:
            logger.warning("Event not found: %s", event_id)
            return None
        return Event(**doc)

    async def lock_event(self, event_id: str, user_id: str) -> Event | None:
        collection = await self._collection()
        doc = await collection.find_one_and_update(
            {"event_id": event_id, "is_locked": False},
            {"$set": {"is_locked": True, "locked_by": user_id, "locked_at": datetime.now(UTC)}},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        if doc:
            logger.info("Event locked: %s", event_id)
        return Event(**doc) if doc else None

    async def finish_event(self, event_id: str) -> Event | None:
        collection = await self._collection()
        doc = await collection.find_one_and_update(
            {"event_id": event_id, "is_finished": False},
            {"$set": {"is_finished": True, "finished_at": datetime.now(UTC)}},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        if doc:
            logger.info("Event finished: %s", event_id)
        return Event(**doc) if doc else None

    async def get_events(self, limit: int = 50, sort_field: str = "timestamp") -> list[Event]:
        collection = await self._collection()
        cursor = collection.find({}, {"_id": 0}).sort(sort_field, -1).limit(limit)
        return [Event(**doc) async for doc in cursor]

    async def delete_event(self, event_id: str) -> bool:
        collection = await self._collection()
        result = await collection.delete_one({"event_id": event_id})
        if result.deleted_count == 1:
            logger.info("Event deleted: %s", event_id)
            return True
        logger.warning("Delete matched no documents for event_id: %s", event_id)
        return False

    async def unlock_event(self, event_id: str, user_id: str) -> Event | None:
        collection = await self._collection()
        doc = await collection.find_one_and_update(
            {"event_id": event_id, "is_locked": True, "locked_by": user_id},
            {"$set": {"is_locked": False, "locked_by": None, "locked_at": None}},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        if doc:
            logger.info("Event unlocked: %s", event_id)
        return Event(**doc) if doc else None
