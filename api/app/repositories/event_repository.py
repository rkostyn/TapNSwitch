from datetime import UTC, date, datetime

from pymongo import ReturnDocument

from app.db.mongo import DB_NAME, MongoClient
from app.logger import get_logger
from app.models.event import Event, EventCreate, EventType, PairingStyle
from app.repositories.documents import new_event_document
from app.services.errors import ConflictError
from app.services.event_filters import event_on_date_mongo_filter, event_search_mongo_filter, merge_mongo_filters
from app.venue import suggested_arena_count

logger = get_logger(__name__)

# Conditional roster writes retry when another device changed the roster
# between the read and the write.
_ROSTER_RETRIES = 5


class RosterConflictError(ConflictError):
    """The roster kept changing underneath a write (409)."""


def event_type_condition(event_type: EventType) -> dict:
    """Query condition for events of ``event_type``. Events stored before
    event types existed have no field and count as standard."""
    if event_type == "standard":
        return {"event_type": {"$in": ["standard", None]}}
    return {"event_type": event_type}


class EventRepository:
    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client

    async def _collection(self):
        return await self.mongo_client.get_collection(DB_NAME, "events")

    async def create_event(self, event_create: EventCreate, created_by: str) -> Event:
        collection = await self._collection()
        doc = new_event_document(
            event_name=event_create.event_name,
            players=event_create.players,
            created_by=created_by,
            start_timestamp=event_create.start_timestamp,
            swiss_matches_per_player=event_create.swiss_matches_per_player,
            swiss_rounds_per_match=event_create.swiss_rounds_per_match,
            suggested_arena_count=suggested_arena_count(len(event_create.players)),
            event_type=event_create.event_type,
        )
        await collection.insert_one(doc)
        logger.info("Event created: %s (%s)", doc["event_id"], doc["event_type"])
        return Event(**doc)

    async def create_checkfront_event(
        self,
        event_create: EventCreate,
        *,
        booking_id: str,
        booking_code: str,
        session_key: str | None,
        item_skus: list[str] | None = None,
        qty: int = 1,
        suggested_count: int | None = None,
        suggested_ids: list[str] | None = None,
    ) -> Event:
        collection = await self._collection()
        players = event_create.players
        doc = new_event_document(
            event_name=event_create.event_name,
            players=players,
            created_by="checkfront",
            start_timestamp=event_create.start_timestamp,
            swiss_matches_per_player=event_create.swiss_matches_per_player,
            swiss_rounds_per_match=event_create.swiss_rounds_per_match,
            suggested_arena_count=suggested_count or suggested_arena_count(max(qty, len(players))),
            suggested_arena_ids=suggested_ids or [],
            event_type="standard",
            checkfront={
                "checkfront_booking_id": booking_id,
                "checkfront_booking_code": booking_code,
                "checkfront_session_key": session_key,
                "checkfront_booking_ids": [booking_id],
                "checkfront_item_skus": item_skus or [],
                "checkfront_qty": qty,
            },
        )
        await collection.insert_one(doc)
        logger.info("Checkfront event created: %s (booking %s)", doc["event_id"], booking_id)
        return Event(**doc)

    async def get_event_by_checkfront_booking_id(self, booking_id: str) -> Event | None:
        collection = await self._collection()
        doc = await collection.find_one({"checkfront_booking_id": booking_id}, {"_id": 0})
        return Event(**doc) if doc else None

    async def get_event_by_checkfront_session_key(self, session_key: str) -> Event | None:
        collection = await self._collection()
        cursor = collection.find(
            {"checkfront_session_key": session_key, "is_finished": False},
            {"_id": 0},
        ).sort("timestamp", -1).limit(1)
        docs = await cursor.to_list(length=1)
        if not docs:
            return None
        return Event(**docs[0])

    async def get_active_checkfront_events(
        self,
        *,
        booking_date: date | None = None,
        search: str | None = None,
    ) -> list[Event]:
        collection = await self._collection()
        filters: list[dict] = [
            {"source": "checkfront", "is_finished": False},
        ]
        if booking_date is not None:
            filters.append(event_on_date_mongo_filter(booking_date))
        search_filter = event_search_mongo_filter(search or "")
        if search_filter:
            filters.append(search_filter)
        query = merge_mongo_filters(*filters)
        cursor = collection.find(query, {"_id": 0}).sort("start_timestamp", 1)
        return [Event(**doc) async for doc in cursor]

    async def get_events_by_user(
        self,
        user_id: str,
        *,
        booking_date: date | None = None,
        search: str | None = None,
    ) -> list[Event]:
        collection = await self._collection()
        filters: list[dict] = [
            {"$or": [{"created_by": user_id}, {"source": "checkfront"}]},
        ]
        if booking_date is not None:
            filters.append(event_on_date_mongo_filter(booking_date))
        search_filter = event_search_mongo_filter(search or "")
        if search_filter:
            filters.append(search_filter)
        query = merge_mongo_filters(*filters)
        cursor = collection.find(query, {"_id": 0}).sort("start_timestamp", 1)
        return [Event(**doc) async for doc in cursor]

    async def get_open_events(self) -> list[Event]:
        collection = await self._collection()
        cursor = collection.find({"is_finished": False}, {"_id": 0}).sort("timestamp", -1)
        return [Event(**doc) async for doc in cursor]

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
            {"$set": {"is_finished": True, "finished_at": datetime.now(UTC), "arena_ids": []}},
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

    async def update_event_fields(self, event_id: str, fields: dict) -> Event | None:
        collection = await self._collection()
        doc = await collection.find_one_and_update(
            {"event_id": event_id},
            {"$set": fields},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        return Event(**doc) if doc else None

    async def update_event_fields_where(self, event_id: str, condition: dict, fields: dict) -> Event | None:
        """``update_event_fields`` that only applies while ``condition`` (on top
        of the event id) holds; None if the event is missing or it no longer does."""
        collection = await self._collection()
        doc = await collection.find_one_and_update(
            {"event_id": event_id, **condition},
            {"$set": fields},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        return Event(**doc) if doc else None

    async def set_event_type(
        self, event_id: str, current: EventType, new: EventType, pairing_style: PairingStyle
    ) -> Event | None:
        """Switch an open event from ``current`` to ``new`` in one conditional
        write that only applies while no group stage or bracket has been
        generated. None if any of that no longer holds; the caller has
        already checked the event has no matches."""
        return await self.update_event_fields_where(
            event_id,
            {
                **event_type_condition(current),
                "is_finished": False,
                "swiss_generated_at": None,
                "bracket_generated_at": None,
            },
            {"event_type": new, "pairing_style": pairing_style},
        )

    async def _update_roster(self, event_id: str, condition: dict, update: dict) -> Event | None:
        """One conditional atomic update of an event's roster. Returns None if
        the event is missing or ``condition`` (on top of the event id) no
        longer holds."""
        collection = await self._collection()
        doc = await collection.find_one_and_update(
            {"event_id": event_id, **condition},
            update,
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        return Event(**doc) if doc else None

    async def add_player(self, event_id: str, player_name: str) -> Event | None:
        """Add a player atomically. ``suggested_arena_count`` is set from the
        new roster size in the same write; the write only applies while the
        roster is the size it was read at, so a concurrent change makes it
        retry rather than store a stale count."""
        for _ in range(_ROSTER_RETRIES):
            event = await self.get_event(event_id)
            if not event:
                return None
            if player_name in event.players:
                raise ValueError("Player is already in the event")
            size = len(event.players)
            updated = await self._update_roster(
                event_id,
                {"players": {"$ne": player_name, "$size": size}},
                {
                    "$addToSet": {"players": player_name},
                    "$set": {"suggested_arena_count": suggested_arena_count(size + 1)},
                },
            )
            if updated:
                logger.info("Player %s added to event %s", player_name, event_id)
                return updated
        raise RosterConflictError("Roster changed too often; try again")

    async def remove_player(self, event_id: str, player_name: str) -> Event | None:
        """Remove a player (and their late flag) atomically; see add_player for
        how ``suggested_arena_count`` stays in step."""
        for _ in range(_ROSTER_RETRIES):
            event = await self.get_event(event_id)
            if not event:
                return None
            if player_name not in event.players:
                raise ValueError("Player is not in the event")
            size = len(event.players)
            remaining = size - event.players.count(player_name)
            updated = await self._update_roster(
                event_id,
                {"players": {"$eq": player_name, "$size": size}},
                {
                    "$pull": {"players": player_name, "late_players": player_name},
                    "$set": {"suggested_arena_count": suggested_arena_count(remaining)},
                },
            )
            if updated:
                logger.info("Player %s removed from event %s", player_name, event_id)
                return updated
        raise RosterConflictError("Roster changed too often; try again")

    async def set_player_late(self, event_id: str, player_name: str, late: bool) -> Event | None:
        """Flag or unflag a player as late in one write that only applies while
        they are on the roster."""
        update = (
            {"$addToSet": {"late_players": player_name}} if late
            else {"$pull": {"late_players": player_name}}
        )
        updated = await self._update_roster(event_id, {"players": player_name}, update)
        if updated:
            logger.info("Player %s marked %s for event %s", player_name, "late" if late else "on-time", event_id)
            return updated
        if not await self.get_event(event_id):
            return None
        raise ValueError("Player is not in the event")

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
