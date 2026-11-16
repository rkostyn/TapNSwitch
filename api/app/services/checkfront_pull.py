from dataclasses import dataclass, field

from app.integrations.checkfront.client import CheckfrontApiClient, CheckfrontApiError
from app.integrations.checkfront.parser import parse_checkfront_payload
from app.logger import get_logger
from app.models.event import Event
from app.repositories.event_repository import EventRepository
from app.services.checkfront_events import sync_checkfront_booking
from app.settings import get_settings

logger = get_logger(__name__)


@dataclass
class CheckfrontPullResult:
    synced: int = 0
    skipped: int = 0
    failed: int = 0
    events: list[Event] = field(default_factory=list)


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
    settings = get_settings()
    player_field_keys = settings.player_field_key_list
    fetch_detail = settings.checkfront_pull_fetch_detail

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

        payload = {"booking/index": {booking_id: entry}}
        if fetch_detail:
            try:
                payload = await api.get_booking(booking_id)
            except CheckfrontApiError:
                logger.warning("Falling back to index data for Checkfront booking %s", booking_id)

        booking = parse_checkfront_payload(payload, player_field_keys=player_field_keys)
        if booking is None:
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
