import os

from pymongo import AsyncMongoClient
from app.logger import get_logger

logger = get_logger(__name__)


class MongoClient:
    def __init__(self):
        self.mongo_uri = os.environ["MONGODB_URI"]
        self.client = AsyncMongoClient(self.mongo_uri,
                                       maxIdleTimeMS=60000,
                                       maxPoolSize=50,
                                       minPoolSize=5,
                                       )


    async def ping(self) -> bool:
        try:
            await self.client.admin.command('ping')
            logger.debug("MongoDB ping successful")
            return True
        except Exception as e:
            logger.error("MongoDB ping failed: %s", e)
            return False

    async def get_database(self, db_name: str) -> AsyncMongoClient:
        return self.client[db_name]

    async def get_collection(self, db_name: str, collection_name: str):
        db = await self.get_database(db_name)
        return db[collection_name]

    async def close(self):
        await self.client.close()


    async def drop_database(self, db_name: str):
        await self.client.drop_database(db_name)

    async def drop_collection(self, db_name: str, collection_name: str):
        db = await self.get_database(db_name)
        await db.drop_collection(collection_name)

    async def create_index(self, db_name: str, collection_name: str, keys: list, unique: bool = False):
        collection = await self.get_collection(db_name, collection_name)
        await collection.create_index(keys, unique=unique)