import json
import re
from datetime import UTC, datetime
from typing import Any

from app.integrations.checkfront.models import CheckfrontBooking

_SKIP_FIELD_KEYS = frozenset({
    "customer_name",
    "customer_first_name",
    "customer_last_name",
    "customer_email",
    "customer_phone",
    "customer_address",
    "customer_city",
    "customer_region",
    "customer_country",
    "customer_postal_zip",
    "customer_email_optin",
    "coachs_name",
    "coach_notes",
    "request",
})

_PLAYER_FIELD_HINTS = ("player", "thrower", "participant", "guest", "member")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _pick_str(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _pick_int(value: Any, default: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _parse_timestamp(value: Any) -> datetime | None:
    if value in (None, "", {}):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError, OSError):
        return None


def _normalize_items(raw_items: Any) -> list[dict[str, Any]]:
    if raw_items is None:
        return []
    if isinstance(raw_items, list):
        return [_as_dict(item) for item in raw_items]
    if isinstance(raw_items, dict):
        item = raw_items.get("item")
        if isinstance(item, list):
            return [_as_dict(entry) for entry in item]
        if isinstance(item, dict):
            return [_as_dict(item)]
        # API detail payloads use line-id keys: {"1": {...}, "2": {...}}
        if any(isinstance(v, dict) for v in raw_items.values()):
            return [_as_dict(v) for v in raw_items.values() if isinstance(v, dict)]
    return []


def _booking_code(booking: dict[str, Any], booking_id: str) -> str | None:
    code = _pick_str(booking, "code")
    if code:
        return code
    # Checkfront API 3.0 booking detail uses `id` for the human booking code
    # (e.g. "YVXL-200626") while `booking_id` is the numeric id.
    candidate = _pick_str(booking, "id")
    if candidate and candidate != booking_id and not candidate.isdigit():
        return candidate
    return None


def _split_name_list(value: str) -> list[str]:
    parts = re.split(r"[\n,;|]+", value)
    return [part.strip() for part in parts if part.strip()]


def _looks_like_player_field(key: str) -> bool:
    lowered = key.casefold()
    if lowered in _SKIP_FIELD_KEYS:
        return False
    if lowered.startswith("customer_"):
        return False
    return any(hint in lowered for hint in _PLAYER_FIELD_HINTS)


def _extract_extra_player_names(fields: dict[str, Any], configured_keys: list[str]) -> list[str]:
    names: list[str] = []
    keys_to_scan = list(configured_keys)
    for key in fields:
        if key not in keys_to_scan and _looks_like_player_field(key):
            keys_to_scan.append(key)

    for key in keys_to_scan:
        raw = fields.get(key)
        if raw in (None, ""):
            continue
        if isinstance(raw, list):
            for entry in raw:
                if entry:
                    names.extend(_split_name_list(str(entry)))
        else:
            names.extend(_split_name_list(str(raw)))
    return names


def _extract_api_booking_record(payload: dict[str, Any]) -> dict[str, Any] | None:
    booking = _as_dict(payload.get("booking"))
    if booking:
        return booking
    index = payload.get("booking/index")
    if isinstance(index, dict) and len(index) == 1:
        return _as_dict(next(iter(index.values())))
    for key, value in payload.items():
        if isinstance(key, str) and key.startswith("booking/") and isinstance(value, dict):
            return value
    return None


def _parse_booking_record(
    booking: dict[str, Any],
    *,
    player_field_keys: list[str] | None = None,
) -> CheckfrontBooking | None:
    attrs = _as_dict(booking.get("@attributes"))
    booking_id = _pick_str(attrs, "booking_id") or _pick_str(booking, "booking_id")
    if not booking_id:
        return None
    code = _booking_code(booking, booking_id)
    status = (_pick_str(booking, "status", "status_id") or "").upper()
    if not code:
        return None

    customer = _as_dict(booking.get("customer"))
    fields = _as_dict(booking.get("fields"))
    meta = _as_dict(booking.get("meta"))
    customer_name = (
        _pick_str(customer, "name", "customer_name")
        or _pick_str(fields, "customer_name", "name")
        or _pick_str(meta, "customer_name", "name")
        or _pick_str(booking, "customer_name")
    )
    if not customer_name:
        return None

    items = _normalize_items(_as_dict(booking.get("order")).get("items"))
    if not items:
        items = _normalize_items(booking.get("items"))
    item_ids: list[str] = []
    item_skus: list[str] = []
    qty_total = 0
    start_date = _parse_timestamp(booking.get("start_date"))

    for item in items:
        item_attrs = _as_dict(item.get("@attributes"))
        item_id = (
            _pick_str(item_attrs, "item_id")
            or _pick_str(item, "item_id")
            or _pick_str(item, "id")
        )
        sku = _pick_str(item, "sku")
        if item_id:
            item_ids.append(item_id)
        if sku:
            item_skus.append(sku)
        qty_total += _pick_int(item.get("qty"))
        item_start = _parse_timestamp(item.get("start_date"))
        if item_start and (start_date is None or item_start < start_date):
            start_date = item_start

    configured_keys = player_field_keys or []
    extra_names = _extract_extra_player_names({**meta, **fields}, configured_keys)

    return CheckfrontBooking(
        booking_id=booking_id,
        code=code,
        status=status,
        customer_name=customer_name,
        customer_email=(
            _pick_str(customer, "email", "customer_email")
            or _pick_str(fields, "customer_email")
            or _pick_str(booking, "customer_email")
        ),
        customer_phone=(
            _pick_str(customer, "phone", "customer_phone")
            or _pick_str(fields, "customer_phone")
            or _pick_str(booking, "customer_phone")
        ),
        start_date=start_date,
        item_ids=item_ids,
        item_skus=item_skus,
        qty=max(qty_total, 1),
        extra_player_names=extra_names,
    )


def parse_checkfront_payload(payload: dict[str, Any], *, player_field_keys: list[str] | None = None) -> CheckfrontBooking | None:
    booking = _extract_api_booking_record(payload)
    if not booking:
        return None
    return _parse_booking_record(booking, player_field_keys=player_field_keys)


def iter_checkfront_index_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    index = payload.get("booking/index")
    if not isinstance(index, dict):
        return []
    return [_as_dict(entry) for entry in index.values()]


def parse_checkfront_body(raw_body: bytes, *, player_field_keys: list[str] | None = None) -> CheckfrontBooking | None:
    if not raw_body:
        return None
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return parse_checkfront_payload(payload, player_field_keys=player_field_keys)
