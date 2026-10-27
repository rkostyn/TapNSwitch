import os

from app.integrations.checkfront.models import CheckfrontBooking
from app.models.event import Event, EventCreate
from app.repositories.event_repository import EventRepository
from app.venue import guess_arena_ids, suggested_arena_count

CHECKFRONT_CREATED_BY = "checkfront"
DEFAULT_ACCEPT_STATUSES = {"PAID", "CONF", "PEND", "HOLD", "WAIT"}


def _configured_statuses() -> set[str]:
    raw = os.getenv("CHECKFRONT_ACCEPT_STATUSES", "")
    if not raw.strip():
        return DEFAULT_ACCEPT_STATUSES
    return {part.strip().upper() for part in raw.split(",") if part.strip()}


def _group_mode() -> str:
    mode = (os.getenv("CHECKFRONT_GROUP_MODE") or "session").strip().lower()
    return mode if mode in {"booking", "session"} else "session"


def _lane_hints(booking: CheckfrontBooking, players: list[str]) -> dict:
    size = max(booking.qty, len(players))
    return {
        "checkfront_item_skus": booking.item_skus,
        "checkfront_qty": booking.qty,
        "suggested_arena_count": suggested_arena_count(size),
        "suggested_arena_ids": guess_arena_ids(*booking.item_skus, booking.event_name),
    }


def _merge_players(existing: list[str], incoming: list[str]) -> list[str]:
    merged = list(existing)
    seen = {name.casefold() for name in merged}
    for name in incoming:
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(name)
    return merged


async def sync_checkfront_booking(repo: EventRepository, booking: CheckfrontBooking) -> Event | None:
    if booking.status and booking.status not in _configured_statuses():
        return None

    players = booking.player_names
    if not players:
        return None

    group_mode = _group_mode()
    if group_mode == "booking":
        existing = await repo.get_event_by_checkfront_booking_id(booking.booking_id)
        if existing:
            if existing.is_finished:
                return existing
            updated_players = _merge_players(existing.players, players)
            fields: dict = {
                "players": updated_players,
                "checkfront_booking_code": booking.code,
                **_lane_hints(booking, updated_players),
            }
            if booking.start_date:
                fields["start_timestamp"] = booking.start_date
            return await repo.update_event_fields(existing.event_id, fields)

        event_create = EventCreate(
            event_name=booking.event_name,
            players=players,
            start_timestamp=booking.start_date,
        )
        hints = _lane_hints(booking, players)
        return await repo.create_checkfront_event(
            event_create,
            booking_id=booking.booking_id,
            booking_code=booking.code,
            session_key=booking.session_key,
            item_skus=hints["checkfront_item_skus"],
            qty=hints["checkfront_qty"],
            suggested_count=hints["suggested_arena_count"],
            suggested_ids=hints["suggested_arena_ids"],
        )

    session_key = booking.session_key
    if session_key:
        existing = await repo.get_event_by_checkfront_session_key(session_key)
        if existing:
            if existing.is_finished:
                return existing
            updated_players = _merge_players(existing.players, players)
            booking_ids = list(existing.checkfront_booking_ids or [])
            if booking.booking_id not in booking_ids:
                booking_ids.append(booking.booking_id)
            return await repo.update_event_fields(
                existing.event_id,
                {
                    "players": updated_players,
                    "checkfront_booking_ids": booking_ids,
                    "checkfront_booking_code": booking.code,
                    **_lane_hints(booking, updated_players),
                },
            )

    existing = await repo.get_event_by_checkfront_booking_id(booking.booking_id)
    if existing:
        if existing.is_finished:
            return existing
        updated_players = _merge_players(existing.players, players)
        return await repo.update_event_fields(
            existing.event_id,
            {
                "players": updated_players,
                "checkfront_booking_code": booking.code,
                **_lane_hints(booking, updated_players),
            },
        )

    event_create = EventCreate(
        event_name=booking.event_name,
        players=players,
        start_timestamp=booking.start_date,
    )
    hints = _lane_hints(booking, players)
    return await repo.create_checkfront_event(
        event_create,
        booking_id=booking.booking_id,
        booking_code=booking.code,
        session_key=session_key,
        item_skus=hints["checkfront_item_skus"],
        qty=hints["checkfront_qty"],
        suggested_count=hints["suggested_arena_count"],
        suggested_ids=hints["suggested_arena_ids"],
    )
