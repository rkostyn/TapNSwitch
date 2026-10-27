import uuid
from datetime import UTC, datetime
from pymongo.errors import DuplicateKeyError
from app.db.mongo import MongoClient
from app.models.player import Player, PlayerCreate
from app.logger import get_logger

logger = get_logger(__name__)


class PlayerRepository:
    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client

    async def _collection(self):
        return await self.mongo_client.get_collection("axes", "players")

    async def create_player(self, player_create: PlayerCreate) -> Player:
        collection = await self._collection()
        existing = await collection.find_one({"player_name": player_create.player_name})
        if existing:
            logger.warning("Player creation failed — name already exists")
            raise ValueError("A player with that name already exists")
        player_id = str(uuid.uuid4())
        created_at = datetime.now(UTC)
        doc = {
            "player_id": player_id,
            "player_name": player_create.player_name,
            "user_id": player_create.user_id,
            "created_at": created_at,
        }
        try:
            await collection.insert_one(doc)
        except DuplicateKeyError:
            logger.warning("Player creation failed — duplicate key conflict")
            raise ValueError("A player with that name already exists")
        logger.info("Player created: %s (name=%s)", player_id, player_create.player_name)
        return Player(**doc)

    async def get_player(self, player_id: str) -> Player | None:
        collection = await self._collection()
        doc = await collection.find_one({"player_id": player_id}, {"_id": 0})
        if not doc:
            logger.warning("Player not found: %s", player_id)
            return None
        return Player(**doc)

    async def get_players(self, limit: int = 100) -> list[Player]:
        collection = await self._collection()
        cursor = collection.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
        return [Player(**doc) async for doc in cursor]

    async def delete_player(self, player_id: str) -> bool:
        collection = await self._collection()
        result = await collection.delete_one({"player_id": player_id})
        if result.deleted_count == 1:
            logger.info("Player deleted: %s", player_id)
            return True
        logger.warning("Delete matched no documents for player_id: %s", player_id)
        return False
