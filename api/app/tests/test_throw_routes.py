import pytest

EVENT_PAYLOAD = {"event_name": "Test Event", "players": ["Alice", "Bob"]}
MATCH_PAYLOAD = {"player_1_id": "player_1", "player_2_id": "player_2", "sequence": 1}
ROUND_PAYLOAD = {"player_1_id": "player_1", "player_2_id": "player_2", "sequence": 1}
THROW_PAYLOAD = {
    "player_id": "test_player",
    "points": 5,
    "clutch_called": False,
    "is_premier": False,
    "is_drop": False,
}


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def make_match(client, auth_token):
    event_id = client.post("/event", json=EVENT_PAYLOAD, headers=auth_headers(auth_token)).json()["event_id"]
    match_id = client.post("/match", json={**MATCH_PAYLOAD, "event_id": event_id}, headers=auth_headers(auth_token)).json()["match_id"]
    return event_id, match_id


def make_round(client, auth_token, match_id):
    return client.post("/round", json={**ROUND_PAYLOAD, "match_id": match_id}, headers=auth_headers(auth_token)).json()["round_id"]


def make_throw_payload(match_id, round_id):
    return {**THROW_PAYLOAD, "match_id": match_id, "round_id": round_id}


def test_submit_throw(client, auth_token):
    _, match_id = make_match(client, auth_token)
    round_id = make_round(client, auth_token, match_id)
    response = client.post("/throw/submit", json=make_throw_payload(match_id, round_id), headers=auth_headers(auth_token))
    assert response.status_code == 200
    assert response.json()["throw_id"]


def test_submit_throw_unauthenticated(client, auth_token):
    _, match_id = make_match(client, auth_token)
    round_id = make_round(client, auth_token, match_id)
    response = client.post("/throw/submit", json=make_throw_payload(match_id, round_id))
    assert response.status_code == 401


def test_submit_throw_match_not_found(client, auth_token):
    response = client.post("/throw/submit", json=make_throw_payload("nonexistent-match", "nonexistent-round"), headers=auth_headers(auth_token))
    assert response.status_code == 404


def test_submit_throw_to_finished_match(client, auth_token):
    _, match_id = make_match(client, auth_token)
    round_id = make_round(client, auth_token, match_id)
    client.post(f"/match/{match_id}/finish", headers=auth_headers(auth_token))
    response = client.post("/throw/submit", json=make_throw_payload(match_id, round_id), headers=auth_headers(auth_token))
    assert response.status_code == 423


def test_submit_throw_to_locked_match_by_owner(client, auth_token):
    _, match_id = make_match(client, auth_token)
    round_id = make_round(client, auth_token, match_id)
    client.post(f"/match/{match_id}/lock", headers=auth_headers(auth_token))
    response = client.post("/throw/submit", json=make_throw_payload(match_id, round_id), headers=auth_headers(auth_token))
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_submit_throw_to_match_locked_by_other(client, auth_token, mongo_client):
    _, match_id = make_match(client, auth_token)
    round_id = make_round(client, auth_token, match_id)
    client.post(f"/match/{match_id}/lock", headers=auth_headers(auth_token))
    collection = await mongo_client.get_collection("axes", "matches")
    await collection.update_one({"match_id": match_id}, {"$set": {"locked_by": "another_user"}})
    response = client.post("/throw/submit", json=make_throw_payload(match_id, round_id), headers=auth_headers(auth_token))
    assert response.status_code == 423


def test_submit_throw_to_finished_event(client, auth_token):
    event_id, match_id = make_match(client, auth_token)
    round_id = make_round(client, auth_token, match_id)
    client.post(f"/event/{event_id}/finish", headers=auth_headers(auth_token))
    response = client.post("/throw/submit", json=make_throw_payload(match_id, round_id), headers=auth_headers(auth_token))
    assert response.status_code == 423


def test_get_throw_by_id(client, auth_token):
    _, match_id = make_match(client, auth_token)
    round_id = make_round(client, auth_token, match_id)
    throw_id = client.post("/throw/submit", json=make_throw_payload(match_id, round_id), headers=auth_headers(auth_token)).json()["throw_id"]
    response = client.get(f"/throw/{throw_id}")
    assert response.status_code == 200
    assert response.json()["throw_id"] == throw_id


def test_search_throws_by_player(client, auth_token):
    _, match_id = make_match(client, auth_token)
    round_id = make_round(client, auth_token, match_id)
    player_id = "search_test_player_functional"
    payload = {**make_throw_payload(match_id, round_id), "player_id": player_id}
    client.post("/throw/submit", json=payload, headers=auth_headers(auth_token))
    response = client.get("/throw/search", params={"player_id": player_id})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(t["player_id"] == player_id for t in data)


def test_search_throws_by_match(client, auth_token):
    _, match_id = make_match(client, auth_token)
    round_id = make_round(client, auth_token, match_id)
    client.post("/throw/submit", json=make_throw_payload(match_id, round_id), headers=auth_headers(auth_token))
    response = client.get("/throw/search", params={"match_id": match_id})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(t["match_id"] == match_id for t in data)


def test_search_throws_no_results(client):
    response = client.get("/throw/search", params={"player_id": "player-that-never-threw"})
    assert response.status_code == 200
    assert response.json() == []


def test_get_throw_not_found(client):
    response = client.get("/throw/nonexistent-throw-id")
    assert response.status_code == 404


def test_delete_throw(client, auth_token):
    _, match_id = make_match(client, auth_token)
    round_id = make_round(client, auth_token, match_id)
    throw_id = client.post("/throw/submit", json=make_throw_payload(match_id, round_id), headers=auth_headers(auth_token)).json()["throw_id"]
    response = client.delete(f"/throw/{throw_id}", headers=auth_headers(auth_token))
    assert response.status_code == 204
    assert client.get(f"/throw/{throw_id}").status_code == 404


def test_delete_throw_not_found(client, auth_token):
    response = client.delete("/throw/nonexistent-throw-id", headers=auth_headers(auth_token))
    assert response.status_code == 404


def test_delete_throw_unauthenticated(client, auth_token):
    _, match_id = make_match(client, auth_token)
    round_id = make_round(client, auth_token, match_id)
    throw_id = client.post("/throw/submit", json=make_throw_payload(match_id, round_id), headers=auth_headers(auth_token)).json()["throw_id"]
    response = client.delete(f"/throw/{throw_id}")
    assert response.status_code == 401


def test_submit_throw_negative_points(client, auth_token):
    _, match_id = make_match(client, auth_token)
    round_id = make_round(client, auth_token, match_id)
    response = client.post(
        "/throw/submit",
        json={**make_throw_payload(match_id, round_id), "points": -1},
        headers=auth_headers(auth_token),
    )
    assert response.status_code == 422


def test_submit_throw_player_id_too_long(client, auth_token):
    _, match_id = make_match(client, auth_token)
    round_id = make_round(client, auth_token, match_id)
    response = client.post(
        "/throw/submit",
        json={**make_throw_payload(match_id, round_id), "player_id": "p" * 65},
        headers=auth_headers(auth_token),
    )
    assert response.status_code == 422


def test_submit_throw_ignores_client_throw_id(client, auth_token):
    _, match_id = make_match(client, auth_token)
    round_id = make_round(client, auth_token, match_id)
    payload = {**make_throw_payload(match_id, round_id), "throw_id": "client-chosen-id"}
    response = client.post("/throw/submit", json=payload, headers=auth_headers(auth_token))
    assert response.status_code == 200
    assert response.json()["throw_id"] != "client-chosen-id"


def test_submit_throw_ignores_client_timestamp(client, auth_token):
    _, match_id = make_match(client, auth_token)
    round_id = make_round(client, auth_token, match_id)
    payload = {**make_throw_payload(match_id, round_id), "timestamp": "2000-01-01T00:00:00"}
    throw_id = client.post("/throw/submit", json=payload, headers=auth_headers(auth_token)).json()["throw_id"]
    throw = client.get(f"/throw/{throw_id}").json()
    assert not throw["timestamp"].startswith("2000-")
