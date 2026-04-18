
from fastapi import Body, APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from app.db.mongo import MongoClient
import base64
import binascii
import hashlib

from app.dependencies import bearer_scheme, create_access_token, create_refresh_token, get_current_user, get_mongo_client, get_redis_client, rate_limit
from app.db.redis import RedisClient
from app.repositories.user_repository import UserRepository
from app.models.user import User, UserCreate
from app.models.auth import RegisterRequest, RegisterResponse, LoginRequest, RefreshRequest, TokenResponse
from app.logger import get_logger

logger = get_logger(__name__)


router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)

@router.post("/register", response_model=RegisterResponse, dependencies=[Depends(rate_limit(5, 60))])
async def register(body: RegisterRequest = Body(...), mongo_client: MongoClient = Depends(get_mongo_client)):
    logger.info("Register attempt")
    db = await mongo_client.get_database('axes')
    # Check if registration token is valid
    token_doc = await db['registration_tokens'].find_one({"token": body.registration_token})
    if not token_doc:
        logger.warning("Invalid registration token")
        raise HTTPException(status_code=400, detail="Invalid registration token")
    # Create user — only consume the token after success so failures don't burn it
    repo = UserRepository(mongo_client)
    try:
        user_create = UserCreate(
            user_name=body.username,
            email=body.email,
            password=body.password,
            registration_token=body.registration_token
        )
        user = await repo.create_user(user_create)
        await db['registration_tokens'].delete_one({"token": body.registration_token})
        logger.info("User registered successfully")
        return RegisterResponse(
            user_id=user.user_id,
            username=user.user_name,
            email=user.email
        )
    except ValueError as e:
        logger.warning("Registration failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(rate_limit(10, 60))])
async def login(body: LoginRequest, mongo_client: MongoClient = Depends(get_mongo_client), redis_client: RedisClient = Depends(get_redis_client)):
    """
    The body of the request should contain your username and password, base64 encoded together. For example: "username:password | base64"
    """
    try:
        decoded = base64.b64decode(body.credentials).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        logger.warning("Login attempt with malformed base64 credentials")
        raise HTTPException(status_code=400, detail="Invalid base64 credentials")

    if ":" not in decoded:
        logger.warning("Login attempt with missing credentials separator")
        raise HTTPException(status_code=400, detail="Credentials must be user:pass")

    username, password = decoded.split(":", 1)
    logger.info("Login attempt")
    repo = UserRepository(mongo_client)
    if not await repo.verify_user(username, password):
        logger.warning("Failed login attempt")
        raise HTTPException(status_code=401, detail="Invalid username or password")

    access_token = await create_access_token(subject=username, redis_client=redis_client, expires_seconds=3600)
    refresh_token = await create_refresh_token(subject=username, redis_client=redis_client)
    # Store a link from the access token to the refresh token so logout can revoke both
    access_hash = hashlib.sha256(access_token.encode()).hexdigest()
    refresh_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    await redis_client.set(f"auth:token_refresh:{access_hash}", refresh_hash, expire=3600)
    logger.info("Login successful")
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(rate_limit(10, 60))])
async def refresh(body: RefreshRequest, redis_client: RedisClient = Depends(get_redis_client)):
    refresh_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()
    subject = await redis_client.get(f"auth:refresh_token:{refresh_hash}")
    if subject is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    access_token = await create_access_token(subject=subject, redis_client=redis_client, expires_seconds=3600)
    access_hash = hashlib.sha256(access_token.encode()).hexdigest()
    await redis_client.set(f"auth:token_refresh:{access_hash}", refresh_hash, expire=3600)
    logger.info("Token refreshed for %s", subject)
    return TokenResponse(access_token=access_token, refresh_token=body.refresh_token)


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    redis_client: RedisClient = Depends(get_redis_client),
):
    access_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    refresh_hash = await redis_client.get(f"auth:token_refresh:{access_hash}")
    await redis_client.delete(f"auth:token:{access_hash}")
    await redis_client.delete(f"auth:token_refresh:{access_hash}")
    if refresh_hash:
        await redis_client.delete(f"auth:refresh_token:{refresh_hash}")
    logger.info("User logged out")
    return {"message": "ok"}


@router.get("/user", response_model=User)
async def get_user(
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    """
    Retrieve information about the currently authenticated user
    """
    repo = UserRepository(mongo_client)
    user = await repo.get_user(current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user