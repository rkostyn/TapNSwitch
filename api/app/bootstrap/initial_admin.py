import os

from app.db.mongo import MongoClient
from app.logger import get_logger
from app.repositories.user_repository import UserRepository

logger = get_logger(__name__)


async def ensure_initial_admin(mongo_client: MongoClient) -> None:
    """
    If the database has no admin user yet, create one from INITIAL_ADMIN_* env vars.

    Skips when any user has is_admin=True, or when INITIAL_ADMIN_PASSWORD is unset/empty.
    """
    repo = UserRepository(mongo_client)
    if await repo.has_any_admin():
        logger.debug("Initial admin bootstrap skipped: an admin user already exists")
        return

    password = (os.getenv("INITIAL_ADMIN_PASSWORD") or "").strip()
    if not password:
        logger.warning(
            "No admin users in database; set INITIAL_ADMIN_PASSWORD to create the first admin on startup"
        )
        return

    username = (os.getenv("INITIAL_ADMIN_USERNAME") or "admin").strip() or "admin"
    email = (os.getenv("INITIAL_ADMIN_EMAIL") or "admin@local.dev").strip() or "admin@local.dev"

    try:
        await repo.create_user_admin(username, email, password, is_admin=True)
        logger.info("Created initial admin user (user_name=%s)", username)
    except ValueError as e:
        if "already exists" in str(e).lower():
            logger.warning(
                "INITIAL_ADMIN_PASSWORD is set but initial admin was not created: %s",
                e,
            )
        else:
            raise
