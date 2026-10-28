import pytest

from app.integrations.checkfront.parser import parse_checkfront_payload
from app.services.checkfront_events import sync_checkfront_booking
from app.repositories.event_repository import EventRepository
from app.tests.fakes import FakeMongoClient


SAMPLE_BOOKING = {
    "@attributes": {"version": "3.0", "host": "urbanaxes.checkfront.com"},
    "booking": {
        "@attributes": {"booking_id": "157"},
        "status": "PAID",
        "code": "KMVQ-060314",
        "start_date": "1394128800",
        "end_date": "1394128800",
        "customer": {
            "code": "BT5-386-579",
            "name": "Jordan Smith",
            "email": "jordan@example.com",
            "region": "MD",
            "address": "1 N Haven St",
            "city": "Baltimore",
            "country": "US",
            "phone": "240-555-0100",
            "postal_zip": "21224",
        },
        "fields": {
            "customer_name": "Jordan Smith",
            "customer_email": "jordan@example.com",
            "customer_region": "MD",
            "customer_address": "1 N Haven St",
            "customer_city": "Baltimore",
            "customer_country": "US",
            "customer_phone": "240-555-0100",
            "customer_postal_zip": "21224",
        },
        "order": {
            "items": {
                "item": {
                    "@attributes": {"line_id": "1", "item_id": "42"},
                    "start_date": "1394128800",
                    "end_date": "1394128800",
                    "sku": "private-event-2hr",
                    "status": "PAID",
                    "qty": "1",
                }
            }
        },
    },
}


def test_parse_checkfront_payload_extracts_customer_name():
    booking = parse_checkfront_payload(SAMPLE_BOOKING)
    assert booking is not None
    assert booking.customer_name == "Jordan Smith"
    assert booking.code == "KMVQ-060314"
    assert booking.booking_id == "157"
    assert booking.player_names == ["Jordan Smith"]


def test_parse_checkfront_payload_supports_extra_player_field():
    payload = {
        "booking": {
            **SAMPLE_BOOKING["booking"],
            "fields": {
                **SAMPLE_BOOKING["booking"]["fields"],
                "thrower_names": "Alex Lee, Casey Morgan",
            },
        }
    }
    booking = parse_checkfront_payload(payload, player_field_keys=["thrower_names"])
    assert booking is not None
    assert booking.player_names == ["Jordan Smith", "Alex Lee", "Casey Morgan"]


@pytest.mark.asyncio
async def test_sync_checkfront_booking_creates_event(monkeypatch):
    monkeypatch.setenv("CHECKFRONT_GROUP_MODE", "booking")
    repo = EventRepository(FakeMongoClient())
    booking = parse_checkfront_payload(SAMPLE_BOOKING)
    assert booking is not None

    event = await sync_checkfront_booking(repo, booking)
    assert event is not None
    assert event.source == "checkfront"
    assert event.players == ["Jordan Smith"]
    assert event.checkfront_booking_code == "KMVQ-060314"


@pytest.mark.asyncio
async def test_sync_checkfront_booking_session_mode_merges_names(monkeypatch):
    monkeypatch.setenv("CHECKFRONT_GROUP_MODE", "session")
    repo = EventRepository(FakeMongoClient())

    first = parse_checkfront_payload(SAMPLE_BOOKING)
    second_payload = {
        "booking": {
            **SAMPLE_BOOKING["booking"],
            "@attributes": {"booking_id": "158"},
            "code": "KMVQ-060315",
            "customer": {
                "name": "Alex Lee",
                "email": "alex@example.com",
            },
            "fields": {"customer_name": "Alex Lee"},
        }
    }
    second = parse_checkfront_payload(second_payload)

    event_one = await sync_checkfront_booking(repo, first)
    event_two = await sync_checkfront_booking(repo, second)

    assert event_one is not None
    assert event_two is not None
    assert event_one.event_id == event_two.event_id
    assert event_two.players == ["Jordan Smith", "Alex Lee"]


def test_checkfront_webhook_requires_secret(client, monkeypatch):
    monkeypatch.delenv("CHECKFRONT_WEBHOOK_SECRET", raising=False)
    response = client.post("/integrations/checkfront/webhook", json=SAMPLE_BOOKING)
    assert response.status_code == 503


def test_checkfront_webhook_creates_event(client, monkeypatch):
    monkeypatch.setenv("CHECKFRONT_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("CHECKFRONT_GROUP_MODE", "booking")
    response = client.post(
        "/integrations/checkfront/webhook",
        json=SAMPLE_BOOKING,
        headers={"X-Checkfront-Webhook-Key": "test-secret"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "checkfront"
    assert data["players"] == ["Jordan Smith"]


API_INDEX_ENTRY = {
    "booking_id": 157,
    "code": "KMVQ-060314",
    "status_id": "PAID",
    "customer_name": "Jordan Smith",
    "customer_email": "jordan@example.com",
    "summary": "Private Event 2Hr",
    "date_desc": "Thu Jun 11, 2026",
}

API_BOOKING_DETAIL = {
    "booking/157": {
        **API_INDEX_ENTRY,
        "start_date": 1394128800,
        "fields": {"customer_name": "Jordan Smith"},
        "items": {
            "item": {
                "item_id": "42",
                "sku": "private-event-2hr",
                "qty": "1",
                "start_date": "1394128800",
            }
        },
    }
}

# Real Checkfront API 3.0 detail shape (Baltimore): code lives in `id`,
# items are keyed by line number, customer fields may live in `meta`.
API_BOOKING_DETAIL_V3 = {
    "version": "3.0",
    "request": {"status": "OK", "resource": "booking", "id": "39811"},
    "booking": {
        "id": "YVXL-200626",
        "booking_id": 39811,
        "status_id": "PAID",
        "customer_name": "Jordan Smith",
        "customer_email": "jordan@example.com",
        "start_date": 1784152800,
        "end_date": 1784167200,
        "meta": {
            "customer_name": "Jordan Smith",
            "customer_first_name": "Jordan",
            "customer_last_name": "Smith",
        },
        "items": {
            "1": {
                "status_id": "PAID",
                "id": 20,
                "sku": "private-event-2hr",
                "qty": "2",
                "start_date": 1784152800,
            }
        },
    },
}


def test_parse_checkfront_api_index_entry():
    booking = parse_checkfront_payload({"booking/index": {"157": API_INDEX_ENTRY}})
    assert booking is not None
    assert booking.customer_name == "Jordan Smith"
    assert booking.status == "PAID"


def test_parse_checkfront_api_booking_detail():
    booking = parse_checkfront_payload(API_BOOKING_DETAIL)
    assert booking is not None
    assert booking.item_skus == ["private-event-2hr"]


def test_parse_checkfront_api_booking_detail_v3_shape():
    booking = parse_checkfront_payload(API_BOOKING_DETAIL_V3)
    assert booking is not None
    assert booking.booking_id == "39811"
    assert booking.code == "YVXL-200626"
    assert booking.customer_name == "Jordan Smith"
    assert booking.item_skus == ["private-event-2hr"]
    assert booking.item_ids == ["20"]
    assert booking.qty == 2
    assert booking.event_name == "Jordan Smith (YVXL-200626)"


def test_parse_uses_first_and_last_when_customer_name_missing():
    payload = {
        "booking": {
            "booking_id": 401,
            "id": "REAL-281026",
            "status_id": "STOP",
            "meta": {
                "customer_first_name": "Taylor",
                "customer_last_name": "Nguyen",
            },
            "items": {"1": {"id": 20, "sku": "open-throw-1hr", "qty": "1"}},
        }
    }
    booking = parse_checkfront_payload(payload)
    assert booking is not None
    assert booking.customer_name == "Taylor Nguyen"
    assert booking.status == "STOP"


def test_parse_keeps_booking_without_customer_using_code():
    payload = {
        "booking": {
            "booking_id": 402,
            "code": "WALK-281026",
            "status_id": "PAID",
            "items": {"1": {"id": 21, "sku": "walk-in-1hr", "qty": "4"}},
        }
    }
    booking = parse_checkfront_payload(payload)
    assert booking is not None
    assert booking.customer_name == "WALK-281026"
    assert booking.player_names == ["WALK-281026"]


def test_parse_unwraps_field_value_dicts():
    payload = {
        "booking": {
            **SAMPLE_BOOKING["booking"],
            "fields": {
                **SAMPLE_BOOKING["booking"]["fields"],
                "thrower_names": {"value": "Alex Lee, Casey Morgan"},
            },
        }
    }
    booking = parse_checkfront_payload(payload, player_field_keys=["thrower_names"])
    assert booking is not None
    assert "Alex Lee" in booking.player_names
    assert "Casey Morgan" in booking.player_names


@pytest.mark.asyncio
async def test_sync_keeps_real_customer_on_placeholder_sku(monkeypatch):
    monkeypatch.setenv("CHECKFRONT_GROUP_MODE", "booking")
    repo = EventRepository(FakeMongoClient())
    payload = {
        "booking": {
            "booking_id": 404,
            "code": "HPJF-140826",
            "status_id": "PAID",
            "customer_name": "Brian Party",
            "items": {"1": {"id": 9, "sku": "walkinplaceholder", "qty": "6"}},
        }
    }
    booking = parse_checkfront_payload(payload)
    event = await sync_checkfront_booking(repo, booking)
    assert event is not None
    assert event.event_name == "Brian Party (HPJF-140826)"
    assert event.players == ["Brian Party"]


@pytest.mark.asyncio
async def test_sync_skips_placeholder_bookings(monkeypatch):
    monkeypatch.setenv("CHECKFRONT_GROUP_MODE", "booking")
    repo = EventRepository(FakeMongoClient())
    payload = {
        "booking": {
            "booking_id": 403,
            "code": "NSKZ-200626",
            "status_id": "PAID",
            "customer_name": "Leagueplaceholder",
            "items": {"1": {"id": 9, "sku": "leagueplaceholder", "qty": "1"}},
        }
    }
    booking = parse_checkfront_payload(payload)
    event = await sync_checkfront_booking(repo, booking)
    assert event is None


@pytest.mark.asyncio
async def test_sync_accepts_arrived_stop_status(monkeypatch):
    monkeypatch.setenv("CHECKFRONT_GROUP_MODE", "booking")
    repo = EventRepository(FakeMongoClient())
    payload = {
        "booking": {
            **SAMPLE_BOOKING["booking"],
            "status": "STOP",
        }
    }
    booking = parse_checkfront_payload(payload)
    event = await sync_checkfront_booking(repo, booking)
    assert event is not None
    assert event.players == ["Jordan Smith"]


@pytest.mark.asyncio
async def test_pull_checkfront_bookings(monkeypatch):
    monkeypatch.setenv("CHECKFRONT_GROUP_MODE", "booking")

    class FakeApi:
        async def list_bookings(self, *, start_date="today", status_id=None):
            return [API_INDEX_ENTRY]

        async def get_booking(self, booking_id: str):
            return API_BOOKING_DETAIL

    repo = EventRepository(FakeMongoClient())
    from app.services.checkfront_pull import pull_checkfront_bookings

    result = await pull_checkfront_bookings(repo, client=FakeApi())
    assert result.synced == 1
    assert result.events[0].players == ["Jordan Smith"]


def test_checkfront_sync_requires_auth(client, monkeypatch):
    monkeypatch.setenv("CHECKFRONT_API_URL", "https://example.checkfront.com/api/3.0")
    monkeypatch.setenv("CHECKFRONT_API_KEY", "key")
    monkeypatch.setenv("CHECKFRONT_API_SECRET", "secret")
    response = client.post("/integrations/checkfront/sync")
    assert response.status_code in {401, 403}


def test_checkfront_status_requires_auth(client):
    response = client.get("/integrations/checkfront/status")
    assert response.status_code in {401, 403}


def test_checkfront_status_reports_configuration(client, monkeypatch, auth_token):
    monkeypatch.setenv("CHECKFRONT_API_URL", "https://urbanaxesbaltimore.checkfront.com/api/3.0")
    monkeypatch.setenv("CHECKFRONT_API_KEY", "key")
    monkeypatch.setenv("CHECKFRONT_API_SECRET", "secret")
    monkeypatch.setenv("CHECKFRONT_SYNC_INTERVAL_SECONDS", "300")
    monkeypatch.setenv("CHECKFRONT_GROUP_MODE", "booking")

    response = client.get(
        "/integrations/checkfront/status",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is True
    assert data["poll_enabled"] is True
    assert data["sync_interval_seconds"] == 300
    assert data["group_mode"] == "booking"
    assert "urbanaxesbaltimore" in data["api_url"]
