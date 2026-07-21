from app.db.mongo import MongoClient
from app.logger import get_logger
from app.models.venue import Arena
from app.services.venue_config import DEFAULT_VENUE_ID, default_arenas_from_env

logger = get_logger(__name__)


class VenueRepository:
    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client

    async def _collection(self):
        return await self.mongo_client.get_collection("axes", "venue_settings")

    async def get_arenas(self) -> list[Arena]:
        collection = await self._collection()
        doc = await collection.find_one({"venue_id": DEFAULT_VENUE_ID}, {"_id": 0, "arenas": 1})
        if not doc or not doc.get("arenas"):
            return default_arenas_from_env()
        return [Arena(**entry) for entry in doc["arenas"]]

    async def set_arenas(self, arenas: list[Arena]) -> list[Arena]:
        collection = await self._collection()
        payload = [arena.model_dump() for arena in arenas]
        await collection.update_one(
            {"venue_id": DEFAULT_VENUE_ID},
            {"$set": {"venue_id": DEFAULT_VENUE_ID, "arenas": payload}},
            upsert=True,
        )
        logger.info("Updated venue arenas (%d lanes)", len(arenas))
        return arenas
