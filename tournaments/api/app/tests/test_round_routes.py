import pytest

EVENT_PAYLOAD = {"event_name": "Test Event", "players": ["Alice", "Bob"]}
MATCH_PAYLOAD = {"player_1_id": "player_1", "player_2_id": "player_2", "sequence": 1}
ROUND_PAYLOAD = {"player_1_id": "player_1", "player_2_id": "player_2", "sequence": 1}


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def make_match(client, auth_token):
    event_id = client.post("/event", json=EVENT_PAYLOAD, headers=auth_headers(auth_token)).json()["event_id"]
    return client.post("/match", json={**MATCH_PAYLOAD, "event_id": event_id}, headers=auth_headers(auth_token)).json()["match_id"]


def test_create_round(client, auth_token):
    match_id = make_match(client, auth_token)
    response = client.post("/round", json={**ROUND_PAYLOAD, "match_id": match_id}, headers=auth_headers(auth_token))
    assert response.status_code == 200
    data = response.json()
    assert data["round_id"]
    assert data["match_id"] == match_id
    assert data["player_1_id"] == ROUND_PAYLOAD["player_1_id"]
    assert data["sequence"] == ROUND_PAYLOAD["sequence"]
    assert data["is_locked"] is False


def test_create_round_unauthenticated(client, auth_token):
    match_id = make_match(client, auth_token)
    response = client.post("/round", json={**ROUND_PAYLOAD, "match_id": match_id})
    assert response.status_code == 401


def test_get_round(client, auth_token):
    match_id = make_match(client, auth_token)
    round_id = client.post("/round", json={**ROUND_PAYLOAD, "match_id": match_id}, headers=auth_headers(auth_token)).json()["round_id"]
    response = client.get(f"/round/{round_id}")
    assert response.status_code == 200
    assert response.json()["round_id"] == round_id


def test_get_round_not_found(client):
    response = client.get("/round/nonexistent-round-id")
    assert response.status_code == 404


def test_get_rounds_by_match(client, auth_token):
    match_id = make_match(client, auth_token)
    client.post("/round", json={**ROUND_PAYLOAD, "match_id": match_id, "sequence": 1}, headers=auth_headers(auth_token))
    client.post("/round", json={**ROUND_PAYLOAD, "match_id": match_id, "sequence": 2}, headers=auth_headers(auth_token))
    client.post("/round", json={**ROUND_PAYLOAD, "match_id": match_id, "sequence": 3}, headers=auth_headers(auth_token))
    response = client.get(f"/round/match/{match_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert [r["sequence"] for r in data] == [1, 2, 3]


def test_lock_round(client, auth_token):
    match_id = make_match(client, auth_token)
    round_id = client.post("/round", json={**ROUND_PAYLOAD, "match_id": match_id}, headers=auth_headers(auth_token)).json()["round_id"]
    response = client.post(f"/round/{round_id}/lock", headers=auth_headers(auth_token))
    assert response.status_code == 200
    data = response.json()
    assert data["is_locked"] is True
    assert data["locked_by"] == "testuser"
    assert data["locked_at"] is not None


def test_lock_round_already_locked(client, auth_token):
    match_id = make_match(client, auth_token)
    round_id = client.post("/round", json={**ROUND_PAYLOAD, "match_id": match_id}, headers=auth_headers(auth_token)).json()["round_id"]
    client.post(f"/round/{round_id}/lock", headers=auth_headers(auth_token))
    response = client.post(f"/round/{round_id}/lock", headers=auth_headers(auth_token))
    assert response.status_code == 423


def test_unlock_round(client, auth_token):
    match_id = make_match(client, auth_token)
    round_id = client.post("/round", json={**ROUND_PAYLOAD, "match_id": match_id}, headers=auth_headers(auth_token)).json()["round_id"]
    client.post(f"/round/{round_id}/lock", headers=auth_headers(auth_token))
    response = client.post(f"/round/{round_id}/unlock", headers=auth_headers(auth_token))
    assert response.status_code == 200
    data = response.json()
    assert data["is_locked"] is False
    assert data["locked_by"] is None


@pytest.mark.asyncio
async def test_unlock_round_wrong_user(client, auth_token, mongo_client):
    event_id = client.post("/event", json=EVENT_PAYLOAD, headers=auth_headers(auth_token)).json()["event_id"]
    match_id = client.post("/match", json={**MATCH_PAYLOAD, "event_id": event_id}, headers=auth_headers(auth_token)).json()["match_id"]
    round_id = client.post("/round", json={**ROUND_PAYLOAD, "match_id": match_id}, headers=auth_headers(auth_token)).json()["round_id"]
    client.post(f"/round/{round_id}/lock", headers=auth_headers(auth_token))
    collection = await mongo_client.get_collection("axes", "rounds")
    await collection.update_one({"round_id": round_id}, {"$set": {"locked_by": "another_user"}})
    response = client.post(f"/round/{round_id}/unlock", headers=auth_headers(auth_token))
    assert response.status_code == 403


def test_lock_round_not_found(client, auth_token):
    response = client.post("/round/nonexistent-round-id/lock", headers=auth_headers(auth_token))
    assert response.status_code == 404


def test_unlock_round_not_found(client, auth_token):
    response = client.post("/round/nonexistent-round-id/unlock", headers=auth_headers(auth_token))
    assert response.status_code == 404


def test_create_round_match_not_found(client, auth_token):
    response = client.post("/round", json={**ROUND_PAYLOAD, "match_id": "nonexistent-match"}, headers=auth_headers(auth_token))
    assert response.status_code == 404


def test_create_round_in_finished_match(client, auth_token):
    match_id = make_match(client, auth_token)
    client.post(f"/match/{match_id}/finish", headers=auth_headers(auth_token))
    response = client.post("/round", json={**ROUND_PAYLOAD, "match_id": match_id}, headers=auth_headers(auth_token))
    assert response.status_code == 423


@pytest.mark.asyncio
async def test_create_round_in_match_locked_by_other(client, auth_token, mongo_client):
    match_id = make_match(client, auth_token)
    client.post(f"/match/{match_id}/lock", headers=auth_headers(auth_token))
    collection = await mongo_client.get_collection("axes", "matches")
    await collection.update_one({"match_id": match_id}, {"$set": {"locked_by": "another_user"}})
    response = client.post("/round", json={**ROUND_PAYLOAD, "match_id": match_id}, headers=auth_headers(auth_token))
    assert response.status_code == 423


def test_create_round_in_locked_match_by_owner(client, auth_token):
    match_id = make_match(client, auth_token)
    client.post(f"/match/{match_id}/lock", headers=auth_headers(auth_token))
    response = client.post("/round", json={**ROUND_PAYLOAD, "match_id": match_id}, headers=auth_headers(auth_token))
    assert response.status_code == 200


def test_create_round_in_finished_event(client, auth_token):
    event_id = client.post("/event", json=EVENT_PAYLOAD, headers=auth_headers(auth_token)).json()["event_id"]
    match_id = client.post("/match", json={**MATCH_PAYLOAD, "event_id": event_id}, headers=auth_headers(auth_token)).json()["match_id"]
    client.post(f"/event/{event_id}/finish", headers=auth_headers(auth_token))
    response = client.post("/round", json={**ROUND_PAYLOAD, "match_id": match_id}, headers=auth_headers(auth_token))
    assert response.status_code == 423


def test_delete_round(client, auth_token):
    match_id = make_match(client, auth_token)
    round_id = client.post("/round", json={**ROUND_PAYLOAD, "match_id": match_id}, headers=auth_headers(auth_token)).json()["round_id"]
    response = client.delete(f"/round/{round_id}", headers=auth_headers(auth_token))
    assert response.status_code == 204
    assert client.get(f"/round/{round_id}").status_code == 404


def test_delete_round_not_found(client, auth_token):
    response = client.delete("/round/nonexistent-round-id", headers=auth_headers(auth_token))
    assert response.status_code == 404


def test_delete_round_unauthenticated(client, auth_token):
    match_id = make_match(client, auth_token)
    round_id = client.post("/round", json={**ROUND_PAYLOAD, "match_id": match_id}, headers=auth_headers(auth_token)).json()["round_id"]
    response = client.delete(f"/round/{round_id}")
    assert response.status_code == 401


def test_create_round_sequence_zero(client, auth_token):
    match_id = make_match(client, auth_token)
    response = client.post("/round", json={**ROUND_PAYLOAD, "match_id": match_id, "sequence": 0}, headers=auth_headers(auth_token))
    assert response.status_code == 422


def test_create_round_player_id_too_long(client, auth_token):
    match_id = make_match(client, auth_token)
    response = client.post("/round", json={**ROUND_PAYLOAD, "match_id": match_id, "player_1_id": "p" * 65}, headers=auth_headers(auth_token))
    assert response.status_code == 422
