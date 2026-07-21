import os
import re
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo


def venue_timezone() -> ZoneInfo:
    tz_name = (os.getenv("VENUE_TIMEZONE") or os.getenv("CHECKFRONT_TIMEZONE") or "America/New_York").strip()
    return ZoneInfo(tz_name)


def day_bounds_utc(for_date: date, tz: ZoneInfo | None = None) -> tuple[datetime, datetime]:
    tz = tz or venue_timezone()
    start = datetime.combine(for_date, time.min, tzinfo=tz)
    end = datetime.combine(for_date, time.max, tzinfo=tz)
    return start.astimezone(UTC), end.astimezone(UTC)


def event_on_date_mongo_filter(for_date: date) -> dict:
    """Match events whose booking/created time falls on for_date in the venue timezone."""
    start_utc, end_utc = day_bounds_utc(for_date)
    in_range = {"$gte": start_utc, "$lte": end_utc}
    return {
        "$or": [
            {"start_timestamp": in_range},
            {
                "$and": [
                    {"$or": [{"start_timestamp": None}, {"start_timestamp": {"$exists": False}}]},
                    {"timestamp": in_range},
                ]
            },
        ]
    }


def event_search_mongo_filter(search: str) -> dict:
    term = search.strip()
    if not term:
        return {}
    pattern = re.escape(term)
    regex = {"$regex": pattern, "$options": "i"}
    return {
        "$or": [
            {"event_name": regex},
            {"checkfront_booking_code": regex},
            {"players": regex},
        ]
    }


def merge_mongo_filters(*filters: dict) -> dict:
    parts = [f for f in filters if f]
    if not parts:
        return {}
    if len(parts) == 1:
        return parts[0]
    return {"$and": parts}
