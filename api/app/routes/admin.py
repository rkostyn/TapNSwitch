from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import base64
import binascii
import hashlib
import secrets
import string
from datetime import datetime

from app.dependencies import create_access_token, get_mongo_client, get_redis_client
from app.db.redis import RedisClient
from app.repositories.event_repository import EventRepository
from app.repositories.match_repository import MatchRepository
from app.repositories.round_repository import RoundRepository
from app.repositories.throw_repository import ThrowRepository
from app.repositories.player_repository import PlayerRepository
from app.repositories.user_repository import UserRepository
from app.models.event import EventCreate
from app.models.match import MatchCreate
from app.models.round import RoundCreate
from app.models.throw import ThrowSubmit
from app.models.player import PlayerCreate
from app.logger import get_logger
from app.templates import templates

logger = get_logger(__name__)

_COOKIE_NAME = "admin_session"
_LOGIN_REDIRECT = RedirectResponse(url="/admin/login", status_code=302)


_ADMIN_TOKEN_PREFIX = "auth:admin_token"

async def _get_admin_user(request: Request, redis_client: RedisClient) -> str | None:
    token = request.cookies.get(_COOKIE_NAME)
    if not token:
        return None
    return await redis_client.get(f"{_ADMIN_TOKEN_PREFIX}:{hashlib.sha256(token.encode()).hexdigest()}")


# Login routes — no auth dependency
login_router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    default_response_class=HTMLResponse,
    include_in_schema=False,
)

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    default_response_class=HTMLResponse,
    include_in_schema=False,
)


@login_router.get("/login")
async def get_login(request: Request):
    return templates.TemplateResponse(request=request, name="admin/login.html")


@login_router.post("/login")
async def post_login(
    request: Request,
    credentials: str = Form(...),
    mongo_client=Depends(get_mongo_client),
    redis_client: RedisClient = Depends(get_redis_client),
):
    try:
        decoded = base64.b64decode(credentials).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return templates.TemplateResponse(
            request=request, name="admin/login.html", context={"error": "Invalid credentials"}
        )

    if ":" not in decoded:
        return templates.TemplateResponse(
            request=request, name="admin/login.html", context={"error": "Invalid credentials"}
        )

    username, password = decoded.split(":", 1)
    repo = UserRepository(mongo_client)
    if not await repo.verify_user(username, password):
        logger.warning("Failed admin login attempt")
        return templates.TemplateResponse(
            request=request, name="admin/login.html", context={"error": "Invalid username or password"}
        )

    if not await repo.is_admin(username):
        logger.warning("Non-admin user attempted admin login: %s", username)
        return templates.TemplateResponse(
            request=request, name="admin/login.html", context={"error": "Invalid username or password"}
        )

    token = await create_access_token(subject=username, redis_client=redis_client, expires_seconds=3600, key_prefix=_ADMIN_TOKEN_PREFIX)
    logger.info("Admin login successful for %s", username)
    response = RedirectResponse(url="/admin/", status_code=302)
    response.set_cookie(_COOKIE_NAME, token, httponly=True, samesite="strict", secure=True)
    return response


@router.get("/logout")
async def get_logout(request: Request, redis_client: RedisClient = Depends(get_redis_client)):
    token = request.cookies.get(_COOKIE_NAME)
    if token:
        await redis_client.delete(f"{_ADMIN_TOKEN_PREFIX}:{hashlib.sha256(token.encode()).hexdigest()}")
    response = RedirectResponse(url="/admin/login", status_code=302)
    response.delete_cookie(_COOKIE_NAME)
    return response


@router.get("/")
async def get_admin(request: Request, redis_client: RedisClient = Depends(get_redis_client)):
    if not await _get_admin_user(request, redis_client):
        return _LOGIN_REDIRECT
    return templates.TemplateResponse(request=request, name="admin/index.html")


_COLLECTION_ID_FIELD = {
    "events": "event_id",
    "matches": "match_id",
    "rounds": "round_id",
    "throws": "throw_id",
    "users": "user_id",
    "players": "player_id",
}


_PATCH_ALLOWLIST: dict[str, set[str]] = {
    "events":  {"venue_id", "start_timestamp", "is_locked", "locked_by", "locked_at", "is_finished", "finished_at"},
    "matches": {"event_id", "player_1_id", "player_2_id", "sequence", "is_locked", "locked_by", "locked_at", "is_finished", "finished_at"},
    "rounds":  {"match_id", "player_1_id", "player_2_id", "sequence", "is_locked", "locked_by", "locked_at"},
    "throws":  {"match_id", "round_id", "player_id", "event_id", "venue_id", "points", "clutch_called", "is_premier", "is_drop", "timestamp"},
    "players": {"player_name", "user_id"},
    "users":   {"user_name", "email"},
}

_REPO_DELETE = {
    "events":  lambda mc: EventRepository(mc).delete_event,
    "matches": lambda mc: MatchRepository(mc).delete_match,
    "rounds":  lambda mc: RoundRepository(mc).delete_round,
    "throws":  lambda mc: ThrowRepository(mc).delete_throw,
    "players": lambda mc: PlayerRepository(mc).delete_player,
    "users":   lambda mc: UserRepository(mc).delete_user,
}


@router.get("/users/create")
async def get_create_user(request: Request, redis_client: RedisClient = Depends(get_redis_client)):
    if not await _get_admin_user(request, redis_client):
        return _LOGIN_REDIRECT
    return templates.TemplateResponse(request=request, name="admin/create_user.html")


@router.post("/users/create")
async def post_create_user(
    request: Request,
    user_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(""),
    is_admin: str = Form("false"),
    redis_client: RedisClient = Depends(get_redis_client),
    mongo_client=Depends(get_mongo_client),
):
    if not await _get_admin_user(request, redis_client):
        return _LOGIN_REDIRECT

    generated_password = None
    if not password:
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        generated_password = "".join(secrets.choice(alphabet) for _ in range(16))
        password = generated_password

    repo = UserRepository(mongo_client)
    try:
        await repo.create_user_admin(user_name.strip(), email.strip(), password, is_admin=(is_admin == "true"))
    except ValueError as e:
        return templates.TemplateResponse(
            request=request,
            name="admin/create_user.html",
            context={"error": str(e), "user_name": user_name, "email": email},
        )

    if generated_password:
        return templates.TemplateResponse(
            request=request,
            name="admin/create_user.html",
            context={"generated_password": generated_password, "created_user_name": user_name.strip()},
        )

    return RedirectResponse(url="/admin/", status_code=302)


@router.get("/events/create")
async def get_create_event(request: Request, redis_client: RedisClient = Depends(get_redis_client)):
    if not await _get_admin_user(request, redis_client):
        return _LOGIN_REDIRECT
    return templates.TemplateResponse(request=request, name="admin/create_event.html")


@router.post("/events/create")
async def post_create_event(
    request: Request,
    venue_id: str = Form(...),
    start_timestamp: str = Form(""),
    redis_client: RedisClient = Depends(get_redis_client),
    mongo_client=Depends(get_mongo_client),
):
    if not await _get_admin_user(request, redis_client):
        return _LOGIN_REDIRECT

    ts = None
    if start_timestamp:
        try:
            ts = datetime.fromisoformat(start_timestamp)
        except ValueError:
            return templates.TemplateResponse(
                request=request,
                name="admin/create_event.html",
                context={"error": "Invalid timestamp format", "venue_id": venue_id},
            )

    repo = EventRepository(mongo_client)
    await repo.create_event(EventCreate(venue_id=venue_id.strip(), start_timestamp=ts))
    return RedirectResponse(url="/admin/", status_code=302)


@router.post("/create/event")
async def admin_create_event(
    request: Request,
    redis_client: RedisClient = Depends(get_redis_client),
    mongo_client=Depends(get_mongo_client),
):
    if not await _get_admin_user(request, redis_client):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    body = await request.json()
    repo = EventRepository(mongo_client)
    event = await repo.create_event(EventCreate(**body))
    return JSONResponse(status_code=200, content={"event_id": event.event_id})


@router.post("/create/match")
async def admin_create_match(
    request: Request,
    redis_client: RedisClient = Depends(get_redis_client),
    mongo_client=Depends(get_mongo_client),
):
    if not await _get_admin_user(request, redis_client):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    body = await request.json()
    repo = MatchRepository(mongo_client)
    match = await repo.create_match(MatchCreate(**body))
    return JSONResponse(status_code=200, content={"match_id": match.match_id})


@router.post("/create/round")
async def admin_create_round(
    request: Request,
    redis_client: RedisClient = Depends(get_redis_client),
    mongo_client=Depends(get_mongo_client),
):
    if not await _get_admin_user(request, redis_client):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    body = await request.json()
    repo = RoundRepository(mongo_client)
    round_ = await repo.create_round(RoundCreate(**body))
    return JSONResponse(status_code=200, content={"round_id": round_.round_id})


@router.post("/create/throw")
async def admin_create_throw(
    request: Request,
    redis_client: RedisClient = Depends(get_redis_client),
    mongo_client=Depends(get_mongo_client),
):
    if not await _get_admin_user(request, redis_client):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    body = await request.json()
    repo = ThrowRepository(mongo_client)
    result = await repo.submit_throw(ThrowSubmit(**body))
    if result:
        return JSONResponse(status_code=200, content={"throw_id": result["throw_id"]})
    return JSONResponse(status_code=500, content={"detail": "Failed to submit throw"})


@router.post("/create/player")
async def admin_create_player(
    request: Request,
    redis_client: RedisClient = Depends(get_redis_client),
    mongo_client=Depends(get_mongo_client),
):
    if not await _get_admin_user(request, redis_client):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    body = await request.json()
    repo = PlayerRepository(mongo_client)
    try:
        player = await repo.create_player(PlayerCreate(**body))
        return JSONResponse(status_code=200, content={"player_id": player.player_id})
    except ValueError as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})


@router.patch("/{collection}/{doc_id}")
async def patch_admin_doc(
    request: Request,
    collection: str,
    doc_id: str,
    redis_client: RedisClient = Depends(get_redis_client),
    mongo_client=Depends(get_mongo_client),
):
    if not await _get_admin_user(request, redis_client):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    if collection not in _COLLECTION_ID_FIELD:
        return JSONResponse(status_code=404, content={"detail": "Unknown collection"})

    body = await request.json()
    id_field = _COLLECTION_ID_FIELD[collection]
    body = {k: v for k, v in body.items() if k in _PATCH_ALLOWLIST[collection]}

    if not body:
        return JSONResponse(status_code=400, content={"detail": "No fields to update"})

    db_collection = await mongo_client.get_collection("axes", collection)
    existing = await db_collection.find_one({id_field: doc_id}, {"_id": 0})
    if not existing:
        return JSONResponse(status_code=404, content={"detail": "Document not found"})

    # Coerce ISO strings back to datetime for fields that were originally datetimes
    for key, value in body.items():
        if key in existing and isinstance(existing[key], datetime) and isinstance(value, str):
            try:
                body[key] = datetime.fromisoformat(value)
            except ValueError:
                pass

    result = await db_collection.update_one({id_field: doc_id}, {"$set": body})
    if result.matched_count == 0:
        return JSONResponse(status_code=404, content={"detail": "Document not found"})
    return JSONResponse(status_code=200, content={"updated": result.modified_count})


@router.delete("/{collection}/{doc_id}", status_code=204)
async def delete_admin_doc(
    request: Request,
    collection: str,
    doc_id: str,
    redis_client: RedisClient = Depends(get_redis_client),
    mongo_client=Depends(get_mongo_client),
):
    if not await _get_admin_user(request, redis_client):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    if collection not in _REPO_DELETE:
        return JSONResponse(status_code=404, content={"detail": "Unknown collection"})

    delete_fn = _REPO_DELETE[collection](mongo_client)

    # UserRepository.delete_user takes a UserDelete object; all others take a plain id string.
    if collection == "users":
        from app.models.user import UserDelete
        id_field = _COLLECTION_ID_FIELD["users"]
        db_collection = await mongo_client.get_collection("axes", "users")
        user_doc = await db_collection.find_one({id_field: doc_id}, {"_id": 0})
        if not user_doc:
            return JSONResponse(status_code=404, content={"detail": "User not found"})
        deleted = await delete_fn(UserDelete(**user_doc))
    else:
        deleted = await delete_fn(doc_id)

    if not deleted:
        return JSONResponse(status_code=404, content={"detail": "Document not found"})


@router.get("/{collection}/{doc_id}")
async def get_admin_detail(
    request: Request,
    collection: str,
    doc_id: str,
    redis_client: RedisClient = Depends(get_redis_client),
    mongo_client=Depends(get_mongo_client),
):
    if not await _get_admin_user(request, redis_client):
        return _LOGIN_REDIRECT

    if collection not in _COLLECTION_ID_FIELD:
        return templates.TemplateResponse(
            request=request,
            name="admin/detail.html",
            context={"error": f"Unknown collection: {collection}"},
            status_code=404,
        )

    id_field = _COLLECTION_ID_FIELD[collection]
    db_collection = await mongo_client.get_collection("axes", collection)
    exclude = {"_id": 0, "password_hash": 0} if collection == "users" else {"_id": 0}
    doc = await db_collection.find_one({id_field: doc_id}, exclude)

    if not doc:
        return templates.TemplateResponse(
            request=request,
            name="admin/detail.html",
            context={"error": f"Document not found in {collection}"},
            status_code=404,
        )

    doc_js = {k: v.isoformat() if isinstance(v, datetime) else v for k, v in doc.items()}

    return templates.TemplateResponse(
        request=request,
        name="admin/detail.html",
        context={"doc": doc, "collection": collection, "doc_id": doc_id, "id_field": id_field, "doc_js": doc_js},
    )