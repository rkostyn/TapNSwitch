from fastapi import APIRouter, Depends, HTTPException
from app.db.mongo import MongoClient
from app.dependencies import get_mongo_client, get_current_user, rate_limit
from app.repositories.round_repository import RoundRepository
from app.repositories.match_repository import MatchRepository
from app.repositories.event_repository import EventRepository
from app.models.round import Round, RoundCreate
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/round", tags=["Rounds"])


@router.post("", response_model=Round)
async def create_round(
    body: RoundCreate,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    logger.info("Creating round for match %s", body.match_id)
    match_repo = MatchRepository(mongo_client)
    match = await match_repo.get_match(body.match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if match.is_finished:
        raise HTTPException(status_code=423, detail="Match is finished")
    if match.is_locked and match.locked_by != current_user:
        raise HTTPException(status_code=423, detail="Match is locked by another user")
    if match.event_id:
        event_repo = EventRepository(mongo_client)
        event = await event_repo.get_event(match.event_id)
        if event and event.is_finished:
            raise HTTPException(status_code=423, detail="Event is finished")
    repo = RoundRepository(mongo_client)
    return await repo.create_round(body)


@router.get("/match/{match_id}", response_model=list[Round], dependencies=[Depends(rate_limit(60))])
async def get_rounds_by_match(
    match_id: str,
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    logger.info("Fetching rounds for match %s", match_id)
    repo = RoundRepository(mongo_client)
    return await repo.get_rounds_by_match(match_id)


@router.get("/{round_id}", response_model=Round, dependencies=[Depends(rate_limit(60))])
async def get_round(
    round_id: str,
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    logger.info("Fetching round %s", round_id)
    repo = RoundRepository(mongo_client)
    result = await repo.get_round(round_id)
    if not result:
        raise HTTPException(status_code=404, detail="Round not found")
    return result


@router.delete("/{round_id}", status_code=204)
async def delete_round(
    round_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = RoundRepository(mongo_client)
    if not await repo.delete_round(round_id):
        raise HTTPException(status_code=404, detail="Round not found")


@router.post("/{round_id}/lock", response_model=Round)
async def lock_round(
    round_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = RoundRepository(mongo_client)
    existing = await repo.get_round(round_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Round not found")
    result = await repo.lock_round(round_id, current_user)
    if not result:
        logger.warning("Lock attempt on already-locked round %s", round_id)
        raise HTTPException(status_code=423, detail="Round is already locked")
    return result


@router.post("/{round_id}/unlock", response_model=Round)
async def unlock_round(
    round_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = RoundRepository(mongo_client)
    existing = await repo.get_round(round_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Round not found")
    result = await repo.unlock_round(round_id, current_user)
    if not result:
        logger.warning("Unlock attempt failed for round %s — not locked by caller", round_id)
        raise HTTPException(status_code=403, detail="Round is locked by another user")
    return result
