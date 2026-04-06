from fastapi import APIRouter, Depends, HTTPException
from app.db.mongo import MongoClient
from app.dependencies import get_mongo_client, get_current_user, rate_limit
from app.repositories.event_repository import EventRepository
from app.models.event import Event, EventCreate
from app.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/event", tags=["Events"])


@router.post("", response_model=Event)
async def create_event(
    body: EventCreate,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    logger.info("Creating event for venue %s", body.venue_id)
    repo = EventRepository(mongo_client)
    return await repo.create_event(body)


@router.get("/{event_id}", response_model=Event, dependencies=[Depends(rate_limit(60))])
async def get_event(
    event_id: str,
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    logger.info("Fetching event %s", event_id)
    repo = EventRepository(mongo_client)
    result = await repo.get_event(event_id)
    if not result:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.delete("/{event_id}", status_code=204)
async def delete_event(
    event_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    if not await repo.delete_event(event_id):
        raise HTTPException(status_code=404, detail="Event not found")


@router.post("/{event_id}/finish", response_model=Event)
async def finish_event(
    event_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    existing = await repo.get_event(event_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")
    if existing.is_finished:
        raise HTTPException(status_code=423, detail="Event is already finished")
    result = await repo.finish_event(event_id)
    if not result:
        raise HTTPException(status_code=423, detail="Event is already finished")
    return result


@router.post("/{event_id}/lock", response_model=Event)
async def lock_event(
    event_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    existing = await repo.get_event(event_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")
    result = await repo.lock_event(event_id, current_user)
    if not result:
        logger.warning("Lock attempt on already-locked event %s", event_id)
        raise HTTPException(status_code=423, detail="Event is already locked")
    return result


@router.post("/{event_id}/unlock", response_model=Event)
async def unlock_event(
    event_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    existing = await repo.get_event(event_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")
    result = await repo.unlock_event(event_id, current_user)
    if not result:
        logger.warning("Unlock attempt failed for event %s — not locked by caller", event_id)
        raise HTTPException(status_code=403, detail="Event is locked by another user")
    return result
