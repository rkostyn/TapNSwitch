from fastapi import APIRouter, Body, Depends, Header, HTTPException

from app.db.mongo import MongoClient
from app.dependencies import get_current_user, get_mongo_client, rate_limit
from app.logger import get_logger
from app.models.throw import Throw, ThrowGet, ThrowsGet, ThrowSubmit
from app.repositories.match_repository import MatchRepository
from app.repositories.throw_repository import ThrowRepository
from app.services.match_guards import load_scorable_match
from app.services.match_results import update_match_winner

logger = get_logger(__name__)

router = APIRouter(
    prefix="/throw",
    tags=["Throws"],
)

@router.post("/submit", response_model=dict)
async def submit_throw(
    body: ThrowSubmit = Body(...),
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
    x_client_id: str | None = Header(default=None, alias="X-Client-ID", max_length=64),
):
    logger.info("Throw submission for player: %s", body.player_id)
    holder = x_client_id or current_user
    # Finished matches stay editable so coaches can correct scoring afterwards;
    # only a finished event freezes them for good.
    match = await load_scorable_match(mongo_client, body.match_id, holder, allow_finished=True)
    body.throw_id = None
    body.timestamp = None
    r = ThrowRepository(mongo_client)
    success = await r.submit_throw(body)
    if not success:
        logger.error("Throw submission failed for player: %s", body.player_id)
        raise HTTPException(status_code=500, detail="Failed to submit throw")
    logger.info("Throw submitted with ID: %s", success['throw_id'])
    if match.is_finished:
        await update_match_winner(mongo_client, match)
    return {"throw_id": success['throw_id']}


@router.get("/search", response_model=list[Throw], dependencies=[Depends(rate_limit(60))])
async def get_throws_by_criteria(throws_get: ThrowsGet = Depends(), mongo_client: MongoClient = Depends(get_mongo_client)):
    logger.info("Searching throws with criteria: %s", throws_get.model_dump(exclude_none=True))
    r = ThrowRepository(mongo_client)
    throws = await r.get_throws_by_criteria(throws_get)
    logger.info("Found %d throws matching criteria", len(throws))
    return throws


@router.get("/{throw_id}", response_model=Throw, dependencies=[Depends(rate_limit(60))])
async def get_throw_by_id(throw_id: str, mongo_client: MongoClient = Depends(get_mongo_client)):
    logger.info("Fetching throw: %s", throw_id)
    throw_get = ThrowGet(throw_id=throw_id)
    r = ThrowRepository(mongo_client)
    throw = await r.get_throw_by_id(throw_get)
    if not throw:
        logger.warning("Throw not found: %s", throw_id)
        raise HTTPException(status_code=404, detail="Throw not found")
    return throw


@router.delete("/{throw_id}", status_code=204)
async def delete_throw(
    throw_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    r = ThrowRepository(mongo_client)
    existing = await r.get_throw_by_id(ThrowGet(throw_id=throw_id))
    if not existing or not await r.delete_throw(throw_id):
        raise HTTPException(status_code=404, detail="Throw not found")
    # Keep the stored winner honest when scores change after the match ended
    match_repo = MatchRepository(mongo_client)
    match = await match_repo.get_match(existing.match_id)
    if match and match.is_finished:
        await update_match_winner(mongo_client, match)