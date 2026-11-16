from datetime import date as date_type
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.mongo import MongoClient
from app.dependencies import get_current_user, get_mongo_client, rate_limit
from app.logger import get_logger
from app.models.event import (
    BracketGenerate,
    Event,
    EventCreate,
    EventTypeUpdate,
    LateUpdate,
    PlayerAdd,
    SwissConfigUpdate,
    SwissStanding,
)
from app.models.match import Match
from app.repositories.event_repository import EventRepository
from app.services import cascade, event_stages
from app.services.event_filters import venue_timezone
from app.services.event_stages import get_open_event

logger = get_logger(__name__)

router = APIRouter(prefix="/event", tags=["Events"])


@router.post("", response_model=Event)
async def create_event(
    body: EventCreate,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    logger.info("Creating event")
    repo = EventRepository(mongo_client)
    return await repo.create_event(body, current_user)


@router.get("", response_model=list[Event])
async def list_events(
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
    date: date_type | None = Query(
        default=None,
        description="Booking date (YYYY-MM-DD) in venue timezone; defaults to today",
    ),
    q: str | None = Query(default=None, min_length=1, max_length=128, description="Search name, code, or player"),
):
    booking_date = date or datetime.now(venue_timezone()).date()
    logger.info("Listing events for user %s on %s (q=%s)", current_user, booking_date, q)
    repo = EventRepository(mongo_client)
    return await repo.get_events_by_user(current_user, booking_date=booking_date, search=q)


@router.get("/checkfront/active", response_model=list[Event])
async def list_active_checkfront_events(
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
    date: date_type | None = Query(
        default=None,
        description="Booking date (YYYY-MM-DD) in venue timezone; defaults to today",
    ),
    q: str | None = Query(default=None, min_length=1, max_length=128, description="Search name, code, or player"),
):
    """Open Checkfront-imported groups for today's floor — used for the group picker."""
    booking_date = date or datetime.now(venue_timezone()).date()
    repo = EventRepository(mongo_client)
    return await repo.get_active_checkfront_events(booking_date=booking_date, search=q)


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
    if not await cascade.delete_event(mongo_client, event_id):
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


@router.post("/{event_id}/player", response_model=Event)
async def add_player(
    event_id: str,
    body: PlayerAdd,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    await get_open_event(repo, event_id)
    try:
        result = await repo.add_player(event_id, body.player_name)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    if not result:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.delete("/{event_id}/player/{player_name}", response_model=Event)
async def remove_player(
    event_id: str,
    player_name: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    await get_open_event(repo, event_id)
    try:
        result = await repo.remove_player(event_id, player_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if not result:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.put("/{event_id}/player/{player_name}/late", response_model=Event)
async def set_player_late(
    event_id: str,
    player_name: str,
    body: LateUpdate,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    repo = EventRepository(mongo_client)
    await get_open_event(repo, event_id)
    try:
        result = await repo.set_player_late(event_id, player_name, body.late)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if not result:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.put("/{event_id}/type", response_model=Event)
async def set_event_type(
    event_id: str,
    body: EventTypeUpdate,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    return await event_stages.set_event_type(mongo_client, event_id, body.event_type)


@router.put("/{event_id}/swiss-config", response_model=Event)
async def update_swiss_config(
    event_id: str,
    body: SwissConfigUpdate,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    return await event_stages.update_swiss_config(mongo_client, event_id, body.model_dump(exclude_none=True))


@router.post("/{event_id}/swiss/generate", response_model=list[Match])
async def generate_swiss_matches(
    event_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    return await event_stages.generate_swiss_matches(mongo_client, event_id)


@router.post("/{event_id}/swiss/scores", response_model=list[SwissStanding])
async def generate_swiss_scores(
    event_id: str,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    return await event_stages.generate_swiss_standings(mongo_client, event_id)


@router.get("/{event_id}/standings", response_model=list[SwissStanding], dependencies=[Depends(rate_limit(60))])
async def get_standings(
    event_id: str,
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    return await event_stages.get_standings(mongo_client, event_id)


@router.post("/{event_id}/bracket/generate", response_model=list[Match])
async def generate_bracket(
    event_id: str,
    body: BracketGenerate,
    current_user: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    return await event_stages.generate_bracket(mongo_client, event_id, body.rounds_per_match)


@router.get("/{event_id}/bracket", response_model=list[Match], dependencies=[Depends(rate_limit(60))])
async def get_bracket(
    event_id: str,
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    return await event_stages.get_bracket(mongo_client, event_id)


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
