from app.db.mongo import MongoClient
from app.db.redis import RedisClient
from datetime import UTC, datetime
import uuid
from app.logger import get_logger
from app.models.throw import ThrowSubmit, ThrowGet, Throw, ThrowsGet

logger = get_logger(__name__)

class ThrowRepository:
    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.collection = None
        self.redis_client = RedisClient()


    async def submit_throw(self, throw_submit: ThrowSubmit) -> dict:
        collection = await self.mongo_client.get_collection(
            db_name="axes",
            collection_name="throws"
        )
        # Pydantic models are not subscriptable like dicts. Dump to a dict,
        # add the generated throw_id, then insert the dict into Mongo.
        data = throw_submit.model_dump()
        data['throw_id'] = str(uuid.uuid4())
        if data['timestamp'] is None:
            data['timestamp'] = datetime.now(UTC)
        await collection.insert_one(data)
        logger.info("Throw submitted: %s (player=%s)", data['throw_id'], throw_submit.player_id)
        return {"throw_id": data['throw_id']}


    async def get_throw_by_id(self, throw_get: ThrowGet) -> Throw | None:
        collection = await self.mongo_client.get_collection(
            db_name="axes",
            collection_name="throws"
        )
        pipeline = [
            {
                "$match": {
                    "throw_id": throw_get.throw_id
                }
            },
            {
                "$project": {
                    "_id": 0,
                }
            }
        ]
        docs = await collection.aggregate(pipeline)
        doc = await docs.to_list()
        if doc:
            # Construct Pydantic model from the Mongo document using keyword unpacking
            throw_answer = Throw(**doc[0])
            logger.info("Throw found: %s", throw_get.throw_id)
            return throw_answer
        else:
            logger.warning("Throw not found: %s", throw_get.throw_id)
            return None

    async def delete_throw(self, throw_id: str) -> bool:
        collection = await self.mongo_client.get_collection("axes", "throws")
        result = await collection.delete_one({"throw_id": throw_id})
        if result.deleted_count == 1:
            logger.info("Throw deleted: %s", throw_id)
            return True
        logger.warning("Delete matched no documents for throw_id: %s", throw_id)
        return False

    async def get_throws_by_criteria(self, throws_get: ThrowsGet) -> list[Throw]:
        collection = await self.mongo_client.get_collection(
            db_name="axes",
            collection_name="throws"
        )
        pipeline = []
        for field in ThrowsGet.model_fields:
            value = getattr(throws_get, field)
            if value is not None:
                pipeline.append({
                    "$match": {
                        field: value
                    }
                })
        pipeline.append({"$project": {"_id": 0}})
        logger.info("Searching throws with %d filter(s)", len(pipeline) - 1)
        docs = await collection.aggregate(pipeline)
        # Use keyword unpacking when creating Pydantic models from documents
        results = [Throw(**doc) async for doc in docs]
        logger.info("Throw search returned %d result(s)", len(results))
        return results
