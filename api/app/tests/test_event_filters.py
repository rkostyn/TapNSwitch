from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.services.event_filters import day_bounds_utc, event_on_date_mongo_filter, event_search_mongo_filter


def test_day_bounds_utc_eastern():
    tz = ZoneInfo("America/New_York")
    start, end = day_bounds_utc(date(2026, 7, 21), tz)
    # Midnight EDT Jul 21 = 04:00 UTC
    assert start == datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    assert end.hour == 3 and end.minute == 59


def test_event_search_filter_empty():
    assert event_search_mongo_filter("") == {}
    assert event_search_mongo_filter("   ") == {}


def test_event_search_filter_builds_regex():
    filt = event_search_mongo_filter("Brian")
    assert "$or" in filt
    assert filt["$or"][0]["event_name"]["$regex"] == "Brian"


def test_event_on_date_filter_shape():
    filt = event_on_date_mongo_filter(date(2026, 7, 21))
    assert "$or" in filt
    assert len(filt["$or"]) == 2
