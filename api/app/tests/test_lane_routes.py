import pytest

from app.integrations.checkfront.parser import parse_checkfront_payload
from app.repositories.event_repository import EventRepository
from app.services.checkfront_events import sync_checkfront_booking
from app.tests.fakes import FakeMongoClient
from app.tests.test_checkfront_integration import SAMPLE_BOOKING
from app.venue import guess_arena_ids, lane_label, lanes_for_arena_ids, suggested_arena_count


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_suggested_arena_count_matches_baltimore_group_sizes():
    assert suggested_arena_count(4) == 1
    assert suggested_arena_count(6) == 1
    assert suggested_arena_count(8) == 2
    assert suggested_arena_count(10) == 2
    assert suggested_arena_count(16) == 3
    assert suggested_arena_count(24) == 4


def test_lanes_for_arena_ids_expands_each_color_into_two_lanes():
    assert lanes_for_arena_ids(["red"]) == ["red-1", "red-2"]
    assert lanes_for_arena_ids(["red", "green"]) == ["red-1", "red-2", "green-1", "green-2"]
    assert lane_label("red-1") == "Red · Lane 1"


def test_guess_arena_ids_from_checkfront_item_name():
    assert guess_arena_ids("red-arena-2hr") == ["red"]
    assert guess_arena_ids("Private Event 2Hr", "blue-lane") == ["blue"]
    assert guess_arena_ids("private-event-2hr") == []


@pytest.mark.asyncio
async def test_checkfront_sync_stores_lane_hints(monkeypatch):
    monkeypatch.setenv("CHECKFRONT_GROUP_MODE", "booking")
    repo = EventRepository(FakeMongoClient())
    payload = {
        "booking": {
            **SAMPLE_BOOKING["booking"],
            "order": {
                "items": {
                    "item": {
                        "@attributes": {"line_id": "1", "item_id": "42"},
                        "sku": "red-arena-2hr",
                        "qty": "8",
                        "start_date": "1394128800",
                    }
                }
            },
        }
    }
    booking = parse_checkfront_payload(payload)
    event = await sync_checkfront_booking(repo, booking)
    assert event is not None
    assert event.checkfront_item_skus == ["red-arena-2hr"]
    assert event.checkfront_qty == 8
    assert event.suggested_arena_count == 2
    assert event.suggested_arena_ids == ["red"]
    assert event.arena_ids == []


def test_lane_board_requires_auth(client):
    response = client.get("/lanes")
    assert response.status_code in {401, 403}


def test_assign_group_to_arena_and_see_it_on_the_board(client, auth_token):
    event_id = client.post(
        "/event",
        json={"event_name": "Smith party", "players": ["Alex", "Blake", "Casey", "Drew"]},
        headers=auth_headers(auth_token),
    ).json()["event_id"]

    assigned = client.put(
        f"/event/{event_id}/arenas",
        json={"arena_ids": ["red"]},
        headers=auth_headers(auth_token),
    )
    assert assigned.status_code == 200
    assert assigned.json()["arena_ids"] == ["red"]

    board = client.get("/lanes", headers=auth_headers(auth_token))
    assert board.status_code == 200
    data = board.json()
    assert data["venue"] == "Baltimore Urban Axes"
    assert len(data["arenas"]) == 6
    red = next(arena for arena in data["arenas"] if arena["arena_id"] == "red")
    assert [lane["lane_id"] for lane in red["lanes"]] == ["red-1", "red-2"]
    assert red["group"]["event_name"] == "Smith party"
    assert all(event["event_id"] != event_id for event in data["waiting"])


def test_cannot_put_two_groups_on_the_same_arena(client, auth_token):
    first = client.post(
        "/event",
        json={"event_name": "Smith party", "players": ["Alex", "Blake"]},
        headers=auth_headers(auth_token),
    ).json()["event_id"]
    second = client.post(
        "/event",
        json={"event_name": "Lee party", "players": ["Casey", "Drew"]},
        headers=auth_headers(auth_token),
    ).json()["event_id"]

    assert client.put(
        f"/event/{first}/arenas",
        json={"arena_ids": ["green"]},
        headers=auth_headers(auth_token),
    ).status_code == 200

    clash = client.put(
        f"/event/{second}/arenas",
        json={"arena_ids": ["green"]},
        headers=auth_headers(auth_token),
    )
    assert clash.status_code == 409
    assert clash.json()["detail"]["arena_id"] == "green"
    assert clash.json()["detail"]["event_name"] == "Smith party"


def test_unknown_arena_is_rejected(client, auth_token):
    event_id = client.post(
        "/event",
        json={"event_name": "Walk-ins", "players": ["Alex", "Blake"]},
        headers=auth_headers(auth_token),
    ).json()["event_id"]
    response = client.put(
        f"/event/{event_id}/arenas",
        json={"arena_ids": ["purple"]},
        headers=auth_headers(auth_token),
    )
    assert response.status_code == 400


def test_closing_an_event_frees_its_arenas(client, auth_token):
    event_id = client.post(
        "/event",
        json={"event_name": "Smith party", "players": ["Alex", "Blake"]},
        headers=auth_headers(auth_token),
    ).json()["event_id"]
    client.put(
        f"/event/{event_id}/arenas",
        json={"arena_ids": ["blue", "yellow"]},
        headers=auth_headers(auth_token),
    )

    finished = client.post(f"/event/{event_id}/finish", headers=auth_headers(auth_token))
    assert finished.status_code == 200
    assert finished.json()["arena_ids"] == []

    board = client.get("/lanes", headers=auth_headers(auth_token)).json()
    blue = next(arena for arena in board["arenas"] if arena["arena_id"] == "blue")
    assert blue["group"] is None
