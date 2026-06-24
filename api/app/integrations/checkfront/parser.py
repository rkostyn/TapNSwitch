import json
import re
from datetime import UTC, datetime
from typing import Any

from app.integrations.checkfront.models import CheckfrontBooking

_SKIP_FIELD_KEYS = frozenset({
    "customer_name",
    "customer_email",
    "customer_phone",
    "customer_address",
    "customer_city",
    "customer_region",
    "customer_country",
    "customer_postal_zip",
    "request",
})

_PLAYER_FIELD_HINTS = ("player", "thrower", "participant", "guest", "member", "name")


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
    return []


def _split_name_list(value: str) -> list[str]:
    parts = re.split(r"[\n,;|]+", value)
    return [part.strip() for part in parts if part.strip()]


def _looks_like_player_field(key: str) -> bool:
    lowered = key.casefold()
    if lowered in _SKIP_FIELD_KEYS:
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


def parse_checkfront_payload(payload: dict[str, Any], *, player_field_keys: list[str] | None = None) -> CheckfrontBooking | None:
    booking = _as_dict(payload.get("booking"))
    if not booking:
        return None

    attrs = _as_dict(booking.get("@attributes"))
    booking_id = _pick_str(attrs, "booking_id") or _pick_str(booking, "booking_id")
    code = _pick_str(booking, "code")
    status = (_pick_str(booking, "status") or "").upper()
    if not booking_id or not code:
        return None

    customer = _as_dict(booking.get("customer"))
    fields = _as_dict(booking.get("fields"))
    customer_name = (
        _pick_str(customer, "name", "customer_name")
        or _pick_str(fields, "customer_name", "name")
    )
    if not customer_name:
        return None

    items = _normalize_items(_as_dict(booking.get("order")).get("items"))
    item_ids: list[str] = []
    item_skus: list[str] = []
    qty_total = 0
    start_date = _parse_timestamp(booking.get("start_date"))

    for item in items:
        item_attrs = _as_dict(item.get("@attributes"))
        item_id = _pick_str(item_attrs, "item_id") or _pick_str(item, "item_id")
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
    extra_names = _extract_extra_player_names(fields, configured_keys)

    return CheckfrontBooking(
        booking_id=booking_id,
        code=code,
        status=status,
        customer_name=customer_name,
        customer_email=_pick_str(customer, "email", "customer_email") or _pick_str(fields, "customer_email"),
        customer_phone=_pick_str(customer, "phone", "customer_phone") or _pick_str(fields, "customer_phone"),
        start_date=start_date,
        item_ids=item_ids,
        item_skus=item_skus,
        qty=max(qty_total, 1),
        extra_player_names=extra_names,
    )


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
