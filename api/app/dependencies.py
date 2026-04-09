import hashlib
import secrets
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.db.mongo import MongoClient
from app.db.redis import RedisClient
from app.logger import get_logger

logger = get_logger(__name__)

bearer_scheme = HTTPBearer()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def get_mongo_client(request: Request) -> MongoClient:
    return request.app.state.mongo_client


def get_redis_client(request: Request) -> RedisClient:
    return request.app.state.redis_client


def rate_limit(limit: int, window: int = 60):
    async def _check(request: Request):
        client_ip = request.client.host
        key = f"rate_limit:{request.url.path}:{client_ip}"
        redis = get_redis_client(request)
        count = await redis.incr_with_expire(key, window)
        if count > limit:
            logger.warning("Rate limit exceeded for %s on %s", client_ip, request.url.path)
            raise HTTPException(status_code=429, detail="Too many requests")
    return _check


async def create_access_token(subject: str, redis_client: RedisClient, expires_seconds: int = 3600, key_prefix: str = "auth:token") -> str:
    token = secrets.token_urlsafe(32)
    await redis_client.set(f"{key_prefix}:{_hash_token(token)}", subject, expire=expires_seconds)
    logger.info("Access token created")
    return token


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    redis_client: RedisClient = Depends(get_redis_client),
):
    subject = await redis_client.get(f"auth:token:{_hash_token(credentials.credentials)}")
    if subject is None:
        logger.warning("Invalid or expired token presented")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    logger.info("Authenticated user: %s", subject)
    return subject
