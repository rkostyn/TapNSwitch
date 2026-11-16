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


def _event_on_arena(client, auth_token, arena_id, event_type="standard"):
    # Tests share one fake database, so each test uses an arena no other test holds.
    event_id = client.post(
        "/event",
        json={
            "event_name": "Smith party",
            "players": ["Alex", "Blake", "Casey", "Drew"],
            "event_type": event_type,
        },
        headers=auth_headers(auth_token),
    ).json()["event_id"]
    assigned = client.put(
        f"/event/{event_id}/arenas",
        json={"arena_ids": [arena_id]},
        headers=auth_headers(auth_token),
    )
    assert assigned.status_code == 200
    return event_id


def test_swiss_generate_deals_matches_onto_group_lanes(client, auth_token):
    # Tournament events only (ported from the former tournaments/api copy).
    event_id = _event_on_arena(client, auth_token, "black", event_type="tournament")
    board = client.get("/lanes", headers=auth_headers(auth_token)).json()
    black = next(arena for arena in board["arenas"] if arena["arena_id"] == "black")
    assert black["group"]["event_type"] == "tournament"
    matches = client.post(f"/event/{event_id}/swiss/generate", headers=auth_headers(auth_token)).json()
    assert len(matches) == 4  # swiss by default
    assert [m["arena_id"] for m in matches] == ["black-1", "black-2", "black-1", "black-2"]


def test_swiss_generate_without_arenas_leaves_lane_empty(client, auth_token):
    event_id = client.post(
        "/event",
        json={"event_name": "No lanes", "players": ["Alex", "Blake"], "event_type": "tournament"},
        headers=auth_headers(auth_token),
    ).json()["event_id"]
    matches = client.post(f"/event/{event_id}/swiss/generate", headers=auth_headers(auth_token)).json()
    assert matches and all(m["arena_id"] is None for m in matches)


def test_standard_event_does_not_assign_lanes(client, auth_token):
    event_id = _event_on_arena(client, auth_token, "white")
    board = client.get("/lanes", headers=auth_headers(auth_token)).json()
    white = next(arena for arena in board["arenas"] if arena["arena_id"] == "white")
    assert white["group"]["event_type"] == "standard"
    matches = client.post(f"/event/{event_id}/swiss/generate", headers=auth_headers(auth_token)).json()
    assert len(matches) == 6  # round robin on the floor
    assert all(m["arena_id"] is None for m in matches)


def test_waiting_groups_carry_event_type(client, auth_token):
    event_id = client.post(
        "/event",
        json={"event_name": "Waiting tourney", "players": ["Alex", "Blake"], "event_type": "tournament"},
        headers=auth_headers(auth_token),
    ).json()["event_id"]
    board = client.get("/lanes", headers=auth_headers(auth_token)).json()
    waiting = next(group for group in board["waiting"] if group["event_id"] == event_id)
    assert waiting["event_type"] == "tournament"


@pytest.mark.asyncio
async def test_standard_and_tournament_events_coexist():
    """One process, one database: a floor group and a tournament side by side,
    each generating by its own type, including the late-entry path."""
    from app.db.mongo import DB_NAME
    from app.models.event import EventCreate
    from app.repositories.match_repository import MatchRepository
    from app.services.event_stages import generate_swiss_matches
    from app.services.lanes import assign_event_arenas, build_lane_board
    from app.tests.fakes import FakeRedisClient

    mongo = FakeMongoClient()
    redis = FakeRedisClient()
    repo = EventRepository(mongo)
    players = ["Alex", "Blake", "Casey", "Drew"]
    floor = await repo.create_event(EventCreate(event_name="Floor", players=players), "coach")
    tourney = await repo.create_event(
        EventCreate(event_name="Tourney", players=players, event_type="tournament"), "coach"
    )
    floor = await assign_event_arenas(repo, redis, floor, ["red"])
    tourney = await assign_event_arenas(repo, redis, tourney, ["blue", "green"])

    floor_matches = await generate_swiss_matches(mongo, floor.event_id)
    tourney_matches = await generate_swiss_matches(mongo, tourney.event_id)
    assert len(floor_matches) == 6 and all(m.arena_id is None for m in floor_matches)
    assert [m.arena_id for m in tourney_matches] == ["blue-1", "blue-2", "green-1", "green-2"]

    board = await build_lane_board(repo)
    types = {a.arena_id: a.group.event_type for a in board.arenas if a.group}
    assert types == {"red": "standard", "blue": "tournament", "green": "tournament"}

    # Late entry after play has started: tournament deals onto lanes, floor does not.
    throws = await mongo.get_collection(DB_NAME, "throws")
    for event, matches in ((floor, floor_matches), (tourney, tourney_matches)):
        await throws.insert_one({
            "throw_id": f"t-{event.event_id}", "event_id": event.event_id,
            "match_id": matches[0].match_id, "round_id": "r", "player_id": "Alex",
            "points": 5, "timestamp": event.timestamp,
        })
        await repo.add_player(event.event_id, "Eve")
    floor_all = await generate_swiss_matches(mongo, floor.event_id)
    tourney_all = await generate_swiss_matches(mongo, tourney.event_id)
    floor_new = [m for m in floor_all if "Eve" in (m.player_1_id, m.player_2_id)]
    tourney_new = [m for m in tourney_all if "Eve" in (m.player_1_id, m.player_2_id)]
    assert len(floor_new) == 4 and all(m.arena_id is None for m in floor_new)
    assert len(tourney_new) == 2
    assert all(m.arena_id in {"blue-1", "blue-2", "green-1", "green-2"} for m in tourney_new)
    assert len(await MatchRepository(mongo).get_matches_by_event(floor.event_id)) == 10


# ---------------------------------------------------------------------------
# GET /venue
# ---------------------------------------------------------------------------

def test_venue_layout_is_public_and_matches_arenas(client):
    from app.venue import ARENAS, VENUE_NAME

    response = client.get("/venue")
    assert response.status_code == 200
    assert response.json() == {
        "venue": VENUE_NAME,
        "arenas": [
            {
                "arena_id": arena.arena_id,
                "name": arena.name,
                "color": arena.color,
                "text_color": arena.text_color,
                "lanes": [{"lane_id": lane.lane_id, "label": lane.label} for lane in arena.lanes],
            }
            for arena in ARENAS
        ],
    }
    red = response.json()["arenas"][0]
    assert red == {
        "arena_id": "red",
        "name": "Red",
        "color": "#dc2626",
        "text_color": "#ffffff",
        "lanes": [{"lane_id": "red-1", "label": "Lane 1"}, {"lane_id": "red-2", "label": "Lane 2"}],
    }
    assert "group" not in red


def test_venue_is_rate_limited(client, redis_client):
    for key in [k for k in redis_client._counters if k.startswith("rate_limit:/venue:")]:
        redis_client._evict(key)
    statuses = [client.get("/venue").status_code for _ in range(61)]
    assert statuses[:60] == [200] * 60
    assert statuses[60] == 429
    for key in [k for k in redis_client._counters if k.startswith("rate_limit:/venue:")]:
        redis_client._evict(key)
