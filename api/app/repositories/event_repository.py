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

    async def create_event(self, event_create: EventCreate, created_by: str) -> Event:
        collection = await self._collection()
        event_id = str(uuid.uuid4())
        doc = {
            "event_id": event_id,
            "event_name": event_create.event_name,
            "players": event_create.players,
            "late_players": [],
            "created_by": created_by,
            "start_timestamp": event_create.start_timestamp,
            "timestamp": datetime.now(UTC),
            "swiss_matches_per_player": event_create.swiss_matches_per_player,
            "swiss_rounds_per_match": event_create.swiss_rounds_per_match,
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
        await collection.insert_one(doc)
        logger.info("Event created: %s", event_id)
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

    async def get_events_by_user(self, user_id: str) -> list[Event]:
        collection = await self._collection()
        cursor = collection.find({"created_by": user_id}, {"_id": 0}).sort("timestamp", -1)
        return [Event(**doc) async for doc in cursor]

    async def delete_event(self, event_id: str) -> bool:
        collection = await self._collection()
        result = await collection.delete_one({"event_id": event_id})
        if result.deleted_count == 1:
            logger.info("Event deleted: %s", event_id)
            return True
        logger.warning("Delete matched no documents for event_id: %s", event_id)
        return False

    async def update_event_fields(self, event_id: str, fields: dict) -> Event | None:
        collection = await self._collection()
        doc = await collection.find_one_and_update(
            {"event_id": event_id},
            {"$set": fields},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        return Event(**doc) if doc else None

    async def add_player(self, event_id: str, player_name: str) -> Event | None:
        event = await self.get_event(event_id)
        if not event:
            return None
        if player_name in event.players:
            raise ValueError("Player is already in the event")
        updated = await self.update_event_fields(event_id, {"players": event.players + [player_name]})
        if updated:
            logger.info("Player %s added to event %s", player_name, event_id)
        return updated

    async def set_player_late(self, event_id: str, player_name: str, late: bool) -> Event | None:
        event = await self.get_event(event_id)
        if not event:
            return None
        if player_name not in event.players:
            raise ValueError("Player is not in the event")
        late_players = [p for p in event.late_players if p != player_name]
        if late:
            late_players.append(player_name)
        updated = await self.update_event_fields(event_id, {"late_players": late_players})
        if updated:
            logger.info("Player %s marked %s for event %s", player_name, "late" if late else "on-time", event_id)
        return updated

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
