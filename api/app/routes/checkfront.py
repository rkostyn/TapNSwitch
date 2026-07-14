import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.db.mongo import MongoClient
from app.dependencies import get_current_user, get_mongo_client, verify_checkfront_webhook
from app.integrations.checkfront.client import CheckfrontApiClient, CheckfrontApiError
from app.integrations.checkfront.parser import parse_checkfront_body
from app.logger import get_logger
from app.models.event import Event
from app.repositories.event_repository import EventRepository
from app.services.checkfront_events import sync_checkfront_booking
from app.services.checkfront_pull import pull_checkfront_bookings

logger = get_logger(__name__)

router = APIRouter(prefix="/integrations/checkfront", tags=["Checkfront"])


class CheckfrontSyncResponse(BaseModel):
    synced: int
    skipped: int
    failed: int
    events: list[Event]


def _player_field_keys() -> list[str]:
    raw = os.getenv("CHECKFRONT_PLAYER_FIELD_KEYS", "")
    return [part.strip() for part in raw.split(",") if part.strip()]


@router.post("/webhook", response_model=Event)
async def checkfront_webhook(
    request: Request,
    _: None = Depends(verify_checkfront_webhook),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    raw_body = await request.body()
    booking = parse_checkfront_body(raw_body, player_field_keys=_player_field_keys())
    if booking is None:
        raise HTTPException(status_code=400, detail="Unable to parse Checkfront booking payload")

    repo = EventRepository(mongo_client)
    event = await sync_checkfront_booking(repo, booking)
    if event is None:
        return JSONResponse(status_code=202, content={"detail": "Booking ignored", "booking_code": booking.code})

    logger.info(
        "Synced Checkfront booking %s to event %s with %d players",
        booking.code,
        event.event_id,
        len(event.players),
    )
    return event


@router.post("/sync", response_model=CheckfrontSyncResponse)
async def checkfront_sync(
    _: str = Depends(get_current_user),
    mongo_client: MongoClient = Depends(get_mongo_client),
):
    if CheckfrontApiClient.from_env() is None:
        raise HTTPException(status_code=503, detail="Checkfront API credentials are not configured")

    repo = EventRepository(mongo_client)
    try:
        result = await pull_checkfront_bookings(repo)
    except CheckfrontApiError as exc:
        status_code = exc.status_code or 502
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    return CheckfrontSyncResponse(
        synced=result.synced,
        skipped=result.skipped,
        failed=result.failed,
        events=result.events,
    )
