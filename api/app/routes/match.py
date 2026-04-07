from fastapi import APIRouter, Depends, HTTPException
from app.db.mongo import MongoClient
from app.dependencies import get_mongo_client, get_current_user, rate_limit
from app.repositories.match_repository import MatchRepository
from app.repositories.event_repository import EventRepository
from app.models.match import Match, MatchCreate
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/match", tags=["Matches"])


@router.post("", response_model=Match)
async def create_match(
    body: MatchCreate,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    logger.info("Creating match for event %s", body.event_id)
    if body.event_id:
        event_repo = EventRepository(mongo_client)
        event = await event_repo.get_event(body.event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        if event.is_finished:
            raise HTTPException(status_code=423, detail="Event is finished")
        if event.is_locked and event.locked_by != current_user:
            raise HTTPException(status_code=423, detail="Event is locked by another user")
    repo = MatchRepository(mongo_client)
    return await repo.create_match(body)


@router.get("/event/{event_id}", response_model=list[Match], dependencies=[Depends(rate_limit(60))])
async def get_matches_by_event(
    event_id: str,
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    logger.info("Fetching matches for event %s", event_id)
    repo = MatchRepository(mongo_client)
    return await repo.get_matches_by_event(event_id)


@router.get("/{match_id}", response_model=Match, dependencies=[Depends(rate_limit(60))])
async def get_match(
    match_id: str,
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    logger.info("Fetching match %s", match_id)
    repo = MatchRepository(mongo_client)
    result = await repo.get_match(match_id)
    if not result:
        raise HTTPException(status_code=404, detail="Match not found")
    return result


@router.delete("/{match_id}", status_code=204)
async def delete_match(
    match_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = MatchRepository(mongo_client)
    if not await repo.delete_match(match_id):
        raise HTTPException(status_code=404, detail="Match not found")


@router.post("/{match_id}/finish", response_model=Match)
async def finish_match(
    match_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = MatchRepository(mongo_client)
    existing = await repo.get_match(match_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Match not found")
    if existing.is_finished:
        raise HTTPException(status_code=423, detail="Match is already finished")
    result = await repo.finish_match(match_id)
    if not result:
        raise HTTPException(status_code=423, detail="Match is already finished")
    return result


@router.post("/{match_id}/lock", response_model=Match)
async def lock_match(
    match_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = MatchRepository(mongo_client)
    existing = await repo.get_match(match_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Match not found")
    result = await repo.lock_match(match_id, current_user)
    if not result:
        logger.warning("Lock attempt on already-locked match %s", match_id)
        raise HTTPException(status_code=423, detail="Match is already locked")
    return result


@router.post("/{match_id}/unlock", response_model=Match)
async def unlock_match(
    match_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = MatchRepository(mongo_client)
    existing = await repo.get_match(match_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Match not found")
    result = await repo.unlock_match(match_id, current_user)
    if not result:
        logger.warning("Unlock attempt failed for match %s — not locked by caller", match_id)
        raise HTTPException(status_code=403, detail="Match is locked by another user")
    return result
