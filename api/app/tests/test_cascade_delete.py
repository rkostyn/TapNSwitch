"""Deleting an event or match removes its rounds and throws too."""
import pytest

from app.db.mongo import DB_NAME
from app.tests.conftest import _fake_mongo
from app.tests.test_admin_routes import admin_cookies


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _docs(collection, **match):
    docs = _fake_mongo._get_or_create(DB_NAME, collection)._docs
    return [d for d in docs if all(d.get(k) == v for k, v in match.items())]


def _event_with_play(client, token):
    """An event with two matches, each with a round and a throw. Only the
    first throw carries the event id, so both cascade paths are exercised."""
    event_id = client.post(
        "/event", json={"event_name": "Cascade", "players": ["a", "b", "c", "d"]}, headers=_h(token)
    ).json()["event_id"]
    match_ids = []
    for seq, (p1, p2) in enumerate([("a", "b"), ("c", "d")], start=1):
        match_id = client.post(
            "/match",
            json={"event_id": event_id, "player_1_id": p1, "player_2_id": p2, "sequence": seq},
            headers=_h(token),
        ).json()["match_id"]
        round_id = client.post(
            "/round",
            json={"match_id": match_id, "player_1_id": p1, "player_2_id": p2, "sequence": 1},
            headers=_h(token),
        ).json()["round_id"]
        body = {"player_id": p1, "round_id": round_id, "match_id": match_id, "points": 3}
        if seq == 1:
            body["event_id"] = event_id  # throws may or may not carry the event id
        assert client.post("/throw/submit", json=body, headers=_h(token)).status_code == 200
        match_ids.append(match_id)
    return event_id, match_ids


def _assert_gone(event_id, match_ids):
    assert _docs("events", event_id=event_id) == []
    assert _docs("matches", event_id=event_id) == []
    for match_id in match_ids:
        assert _docs("rounds", match_id=match_id) == []
        assert _docs("throws", match_id=match_id) == []
    assert _docs("throws", event_id=event_id) == []


def test_delete_event_removes_matches_rounds_and_throws(client, auth_token):
    event_id, match_ids = _event_with_play(client, auth_token)
    other_event, other_matches = _event_with_play(client, auth_token)

    assert client.delete(f"/event/{event_id}", headers=_h(auth_token)).status_code == 204

    _assert_gone(event_id, match_ids)
    assert len(_docs("matches", event_id=other_event)) == 2
    assert all(_docs("rounds", match_id=m) and _docs("throws", match_id=m) for m in other_matches)


def test_delete_event_twice_is_404(client, auth_token):
    event_id, _ = _event_with_play(client, auth_token)
    assert client.delete(f"/event/{event_id}", headers=_h(auth_token)).status_code == 204
    assert client.delete(f"/event/{event_id}", headers=_h(auth_token)).status_code == 404


def test_delete_match_removes_its_rounds_and_throws_only(client, auth_token):
    event_id, (doomed, kept) = _event_with_play(client, auth_token)

    assert client.delete(f"/match/{doomed}", headers=_h(auth_token)).status_code == 204

    assert _docs("matches", match_id=doomed) == []
    assert _docs("rounds", match_id=doomed) == []
    assert _docs("throws", match_id=doomed) == []
    assert _docs("matches", match_id=kept)
    assert _docs("rounds", match_id=kept) and _docs("throws", match_id=kept)
    assert _docs("events", event_id=event_id)
    assert client.delete(f"/match/{doomed}", headers=_h(auth_token)).status_code == 404


@pytest.mark.parametrize("collection", ["events", "matches"])
def test_admin_delete_cascades(client, auth_token, collection):
    event_id, match_ids = _event_with_play(client, auth_token)
    if collection == "events":
        response = client.delete(f"/admin/events/{event_id}", cookies=admin_cookies())
        assert response.status_code == 204
        _assert_gone(event_id, match_ids)
    else:
        response = client.delete(f"/admin/matches/{match_ids[0]}", cookies=admin_cookies())
        assert response.status_code == 204
        assert _docs("rounds", match_id=match_ids[0]) == []
        assert _docs("throws", match_id=match_ids[0]) == []
        assert _docs("rounds", match_id=match_ids[1])


def test_admin_delete_unknown_event_is_404(client):
    response = client.delete("/admin/events/no-such-event", cookies=admin_cookies())
    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}
