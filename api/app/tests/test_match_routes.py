import pytest

EVENT_PAYLOAD = {"venue_id": "test_venue_1"}
MATCH_PAYLOAD = {
    "player_1_id": "player_1",
    "player_2_id": "player_2",
    "sequence": 1,
}


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def make_event(client, auth_token):
    return client.post("/event", json=EVENT_PAYLOAD, headers=auth_headers(auth_token)).json()["event_id"]


def test_create_match(client, auth_token):
    event_id = make_event(client, auth_token)
    response = client.post("/match", json={**MATCH_PAYLOAD, "event_id": event_id}, headers=auth_headers(auth_token))
    assert response.status_code == 200
    data = response.json()
    assert data["match_id"]
    assert data["event_id"] == event_id
    assert data["player_1_id"] == MATCH_PAYLOAD["player_1_id"]
    assert data["sequence"] == MATCH_PAYLOAD["sequence"]
    assert data["is_locked"] is False


def test_create_match_without_event(client, auth_token):
    response = client.post("/match", json=MATCH_PAYLOAD, headers=auth_headers(auth_token))
    assert response.status_code == 200
    data = response.json()
    assert data["match_id"]
    assert data["event_id"] is None


def test_create_match_unauthenticated(client, auth_token):
    event_id = make_event(client, auth_token)
    response = client.post("/match", json={**MATCH_PAYLOAD, "event_id": event_id})
    assert response.status_code == 401


def test_get_match(client, auth_token):
    event_id = make_event(client, auth_token)
    match_id = client.post("/match", json={**MATCH_PAYLOAD, "event_id": event_id}, headers=auth_headers(auth_token)).json()["match_id"]
    response = client.get(f"/match/{match_id}")
    assert response.status_code == 200
    assert response.json()["match_id"] == match_id


def test_get_match_not_found(client):
    response = client.get("/match/nonexistent-match-id")
    assert response.status_code == 404


def test_get_matches_by_event(client, auth_token):
    event_id = make_event(client, auth_token)
    client.post("/match", json={**MATCH_PAYLOAD, "event_id": event_id, "sequence": 1}, headers=auth_headers(auth_token))
    client.post("/match", json={**MATCH_PAYLOAD, "event_id": event_id, "sequence": 2}, headers=auth_headers(auth_token))
    response = client.get(f"/match/event/{event_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["sequence"] == 1
    assert data[1]["sequence"] == 2


def test_lock_match(client, auth_token):
    event_id = make_event(client, auth_token)
    match_id = client.post("/match", json={**MATCH_PAYLOAD, "event_id": event_id}, headers=auth_headers(auth_token)).json()["match_id"]
    response = client.post(f"/match/{match_id}/lock", headers=auth_headers(auth_token))
    assert response.status_code == 200
    data = response.json()
    assert data["is_locked"] is True
    assert data["locked_by"] == "testuser"
    assert data["locked_at"] is not None


def test_lock_match_already_locked(client, auth_token):
    event_id = make_event(client, auth_token)
    match_id = client.post("/match", json={**MATCH_PAYLOAD, "event_id": event_id}, headers=auth_headers(auth_token)).json()["match_id"]
    client.post(f"/match/{match_id}/lock", headers=auth_headers(auth_token))
    response = client.post(f"/match/{match_id}/lock", headers=auth_headers(auth_token))
    assert response.status_code == 423


def test_unlock_match(client, auth_token):
    event_id = make_event(client, auth_token)
    match_id = client.post("/match", json={**MATCH_PAYLOAD, "event_id": event_id}, headers=auth_headers(auth_token)).json()["match_id"]
    client.post(f"/match/{match_id}/lock", headers=auth_headers(auth_token))
    response = client.post(f"/match/{match_id}/unlock", headers=auth_headers(auth_token))
    assert response.status_code == 200
    data = response.json()
    assert data["is_locked"] is False
    assert data["locked_by"] is None


@pytest.mark.asyncio
async def test_unlock_match_wrong_user(client, auth_token, mongo_client):
    event_id = client.post("/event", json=EVENT_PAYLOAD, headers=auth_headers(auth_token)).json()["event_id"]
    match_id = client.post("/match", json={**MATCH_PAYLOAD, "event_id": event_id}, headers=auth_headers(auth_token)).json()["match_id"]
    client.post(f"/match/{match_id}/lock", headers=auth_headers(auth_token))
    collection = await mongo_client.get_collection("axes", "matches")
    await collection.update_one({"match_id": match_id}, {"$set": {"locked_by": "another_user"}})
    response = client.post(f"/match/{match_id}/unlock", headers=auth_headers(auth_token))
    assert response.status_code == 403


def test_lock_match_not_found(client, auth_token):
    response = client.post("/match/nonexistent-match-id/lock", headers=auth_headers(auth_token))
    assert response.status_code == 404


def test_unlock_match_not_found(client, auth_token):
    response = client.post("/match/nonexistent-match-id/unlock", headers=auth_headers(auth_token))
    assert response.status_code == 404


def test_finish_match(client, auth_token):
    event_id = make_event(client, auth_token)
    match_id = client.post("/match", json={**MATCH_PAYLOAD, "event_id": event_id}, headers=auth_headers(auth_token)).json()["match_id"]
    response = client.post(f"/match/{match_id}/finish", headers=auth_headers(auth_token))
    assert response.status_code == 200
    data = response.json()
    assert data["is_finished"] is True
    assert data["finished_at"] is not None


def test_finish_match_already_finished(client, auth_token):
    event_id = make_event(client, auth_token)
    match_id = client.post("/match", json={**MATCH_PAYLOAD, "event_id": event_id}, headers=auth_headers(auth_token)).json()["match_id"]
    client.post(f"/match/{match_id}/finish", headers=auth_headers(auth_token))
    response = client.post(f"/match/{match_id}/finish", headers=auth_headers(auth_token))
    assert response.status_code == 423


def test_finish_match_not_found(client, auth_token):
    response = client.post("/match/nonexistent-match-id/finish", headers=auth_headers(auth_token))
    assert response.status_code == 404


def test_create_match_in_finished_event(client, auth_token):
    event_id = make_event(client, auth_token)
    client.post(f"/event/{event_id}/finish", headers=auth_headers(auth_token))
    response = client.post("/match", json={**MATCH_PAYLOAD, "event_id": event_id}, headers=auth_headers(auth_token))
    assert response.status_code == 423


@pytest.mark.asyncio
async def test_create_match_in_event_locked_by_other(client, auth_token, mongo_client):
    event_id = make_event(client, auth_token)
    client.post(f"/event/{event_id}/lock", headers=auth_headers(auth_token))
    collection = await mongo_client.get_collection("axes", "events")
    await collection.update_one({"event_id": event_id}, {"$set": {"locked_by": "another_user"}})
    response = client.post("/match", json={**MATCH_PAYLOAD, "event_id": event_id}, headers=auth_headers(auth_token))
    assert response.status_code == 423


def test_create_match_in_locked_event_by_owner(client, auth_token):
    event_id = make_event(client, auth_token)
    client.post(f"/event/{event_id}/lock", headers=auth_headers(auth_token))
    response = client.post("/match", json={**MATCH_PAYLOAD, "event_id": event_id}, headers=auth_headers(auth_token))
    assert response.status_code == 200


def test_delete_match(client, auth_token):
    event_id = make_event(client, auth_token)
    match_id = client.post("/match", json={**MATCH_PAYLOAD, "event_id": event_id}, headers=auth_headers(auth_token)).json()["match_id"]
    response = client.delete(f"/match/{match_id}", headers=auth_headers(auth_token))
    assert response.status_code == 204
    assert client.get(f"/match/{match_id}").status_code == 404


def test_delete_match_not_found(client, auth_token):
    response = client.delete("/match/nonexistent-match-id", headers=auth_headers(auth_token))
    assert response.status_code == 404


def test_delete_match_unauthenticated(client, auth_token):
    event_id = make_event(client, auth_token)
    match_id = client.post("/match", json={**MATCH_PAYLOAD, "event_id": event_id}, headers=auth_headers(auth_token)).json()["match_id"]
    response = client.delete(f"/match/{match_id}")
    assert response.status_code == 401


def test_create_match_sequence_zero(client, auth_token):
    response = client.post("/match", json={**MATCH_PAYLOAD, "sequence": 0}, headers=auth_headers(auth_token))
    assert response.status_code == 422


def test_create_match_player_id_too_long(client, auth_token):
    response = client.post("/match", json={**MATCH_PAYLOAD, "player_1_id": "p" * 65}, headers=auth_headers(auth_token))
    assert response.status_code == 422


def test_create_match_nonexistent_event(client, auth_token):
    response = client.post("/match", json={**MATCH_PAYLOAD, "event_id": "no-such-event"}, headers=auth_headers(auth_token))
    assert response.status_code == 404
