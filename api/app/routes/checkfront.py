import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.db.mongo import MongoClient
from app.dependencies import get_mongo_client, verify_checkfront_webhook
from app.integrations.checkfront.parser import parse_checkfront_body
from app.logger import get_logger
from app.models.event import Event
from app.repositories.event_repository import EventRepository
from app.services.checkfront_events import sync_checkfront_booking

logger = get_logger(__name__)

router = APIRouter(prefix="/integrations/checkfront", tags=["Checkfront"])


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
