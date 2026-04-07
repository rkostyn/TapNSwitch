import uuid
import bcrypt
from pymongo.errors import DuplicateKeyError
from app.db.mongo import MongoClient
from app.models.user import User, UserCreate, UserDelete
from datetime import UTC, datetime
from app.logger import get_logger

logger = get_logger(__name__)

# Used for constant-time dummy comparison when user is not found
_DUMMY_HASH = bcrypt.hashpw(b"dummy", bcrypt.gensalt())


class UserRepository:
    def __init__(self, mongo_client: MongoClient):
        self.mongo_client = mongo_client
        self.collection = None


    async def init_collection(self):
        self.collection = await self.mongo_client.get_collection(
            db_name="axes",
            collection_name="users"
        )

    async def create_user(self, user_create: UserCreate) -> User:
        if self.collection is None:
            await self.init_collection()

        # Check if username or email already exists
        existing_user = await self.collection.find_one({
            "$or": [
                {"user_name": user_create.user_name},
                {"email": user_create.email}
            ]
        })
        if existing_user:
            logger.warning("User creation failed — username or email already exists")
            raise ValueError("Username or email already exists")

        password_hash = bcrypt.hashpw(user_create.password.encode(), bcrypt.gensalt()).decode()
        user_id = str(uuid.uuid4())
        created_at = datetime.now(UTC)

        user_doc = {
            "user_id": user_id,
            "user_name": user_create.user_name,
            "email": user_create.email,
            "password_hash": password_hash,
            "created_at": created_at,
        }
        try:
            result = await self.collection.insert_one(user_doc)
        except DuplicateKeyError:
            logger.warning("User creation failed — duplicate key conflict")
            raise ValueError("Username or email already exists")

        if result.inserted_id:
            logger.info("User created (id=%s)", user_id)
            return User(
                user_id=user_id,
                user_name=user_create.user_name,
                email=user_create.email,
                created_at=created_at,
            )
        else:
            logger.error("Insert returned no inserted_id (id=%s)", user_id)
            raise Exception("Failed to create user")


    async def get_user(self, user_id: str) -> User:
        if self.collection is None:
            await self.init_collection()

        user_doc = await self.collection.find_one({"user_name": user_id})
        if user_doc:
            logger.info("User found: %s", user_id)
            return User(
                user_id=user_doc["user_id"],
                user_name=user_doc["user_name"],
                email=user_doc["email"],
                created_at=user_doc["created_at"]
            )
        else:
            logger.warning("User not found: %s", user_id)
            return None


    async def delete_user(self, user_delete: UserDelete) -> bool:
        if self.collection is None:
            await self.init_collection()

        result = await self.collection.delete_one({
            "user_id": user_delete.user_id
        })
        if result.deleted_count == 1:
            logger.info("User deleted: %s", user_delete.user_id)
            return True
        else:
            logger.warning("Delete matched no documents for user_id: %s", user_delete.user_id)
            return False


    async def verify_user(self, user_name: str, password: str) -> bool:
        if self.collection is None:
            await self.init_collection()

        user_doc = await self.collection.find_one({"user_name": user_name})
        if not user_doc:
            # Always run a comparison to prevent timing-based username enumeration
            bcrypt.checkpw(password.encode(), _DUMMY_HASH)
            logger.warning("Verification failed — user not found")
            return False

        matched = bcrypt.checkpw(password.encode(), user_doc["password_hash"].encode())
        if matched:
            logger.info("User verified")
        else:
            logger.warning("Verification failed — incorrect password")
        return matched

    async def is_admin(self, user_name: str) -> bool:
        if self.collection is None:
            await self.init_collection()

        user_doc = await self.collection.find_one({"user_name": user_name}, {"is_admin": 1})
        return bool(user_doc and user_doc.get("is_admin"))