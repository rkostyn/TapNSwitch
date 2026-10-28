import os
from dataclasses import dataclass, field

from app.integrations.checkfront.client import CheckfrontApiClient, CheckfrontApiError
from app.integrations.checkfront.parser import parse_checkfront_payload
from app.logger import get_logger
from app.models.event import Event
from app.repositories.event_repository import EventRepository
from app.services.checkfront_events import sync_checkfront_booking

logger = get_logger(__name__)


@dataclass
class CheckfrontPullResult:
    synced: int = 0
    skipped: int = 0
    failed: int = 0
    events: list[Event] = field(default_factory=list)


def _player_field_keys() -> list[str]:
    raw = os.getenv("CHECKFRONT_PLAYER_FIELD_KEYS", "")
    return [part.strip() for part in raw.split(",") if part.strip()]


def _fetch_detail() -> bool:
    raw = (os.getenv("CHECKFRONT_PULL_FETCH_DETAIL") or "true").strip().lower()
    return raw not in {"0", "false", "no"}


async def pull_checkfront_bookings(
    repo: EventRepository,
    *,
    client: CheckfrontApiClient | None = None,
    start_date: str = "today",
) -> CheckfrontPullResult:
    api = client or CheckfrontApiClient.from_env()
    if api is None:
        raise CheckfrontApiError("Checkfront API credentials are not configured")

    result = CheckfrontPullResult()
    player_field_keys = _player_field_keys()
    fetch_detail = _fetch_detail()

    try:
        index_entries = await api.list_bookings(start_date=start_date)
    except CheckfrontApiError:
        logger.exception("Failed to list Checkfront bookings for %s", start_date)
        raise

    for entry in index_entries:
        booking_id = str(entry.get("booking_id") or "").strip()
        if not booking_id:
            result.failed += 1
            continue

        index_payload = {"booking/index": {booking_id: entry}}
        index_booking = parse_checkfront_payload(index_payload, player_field_keys=player_field_keys)
        payload = index_payload
        if fetch_detail:
            try:
                payload = await api.get_booking(booking_id)
            except CheckfrontApiError:
                logger.warning("Falling back to index data for Checkfront booking %s", booking_id)
                payload = index_payload

        booking = parse_checkfront_payload(payload, player_field_keys=player_field_keys)
        if booking is None:
            booking = index_booking
        elif index_booking:
            if not booking.customer_name and index_booking.customer_name:
                booking.customer_name = index_booking.customer_name
            if not booking.extra_player_names and index_booking.extra_player_names:
                booking.extra_player_names = index_booking.extra_player_names
            if booking.start_date is None and index_booking.start_date is not None:
                booking.start_date = index_booking.start_date
            if not booking.item_skus and index_booking.item_skus:
                booking.item_skus = index_booking.item_skus
        if booking is None:
            logger.info("Skipping Checkfront booking %s: could not parse", booking_id)
            result.skipped += 1
            continue

        try:
            event = await sync_checkfront_booking(repo, booking)
        except Exception:
            logger.exception("Failed to sync Checkfront booking %s", booking.code)
            result.failed += 1
            continue

        if event is None:
            result.skipped += 1
            continue

        result.synced += 1
        result.events.append(event)

    logger.info(
        "Checkfront pull complete: synced=%d skipped=%d failed=%d",
        result.synced,
        result.skipped,
        result.failed,
    )
    return result
