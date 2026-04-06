import pytest

EVENT_PAYLOAD = {"venue_id": "test_venue_1"}


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_event(client, auth_token):
    response = client.post("/event", json=EVENT_PAYLOAD, headers=auth_headers(auth_token))
    assert response.status_code == 200
    data = response.json()
    assert data["venue_id"] == EVENT_PAYLOAD["venue_id"]
    assert data["event_id"]
    assert data["is_locked"] is False
    assert data["locked_by"] is None


def test_create_event_unauthenticated(client):
    response = client.post("/event", json=EVENT_PAYLOAD)
    assert response.status_code == 401


def test_get_event(client, auth_token):
    event_id = client.post("/event", json=EVENT_PAYLOAD, headers=auth_headers(auth_token)).json()["event_id"]
    response = client.get(f"/event/{event_id}")
    assert response.status_code == 200
    assert response.json()["event_id"] == event_id


def test_get_event_not_found(client):
    response = client.get("/event/nonexistent-event-id")
    assert response.status_code == 404


def test_lock_event(client, auth_token):
    event_id = client.post("/event", json=EVENT_PAYLOAD, headers=auth_headers(auth_token)).json()["event_id"]
    response = client.post(f"/event/{event_id}/lock", headers=auth_headers(auth_token))
    assert response.status_code == 200
    data = response.json()
    assert data["is_locked"] is True
    assert data["locked_by"] == "testuser"
    assert data["locked_at"] is not None


def test_lock_event_already_locked(client, auth_token):
    event_id = client.post("/event", json=EVENT_PAYLOAD, headers=auth_headers(auth_token)).json()["event_id"]
    client.post(f"/event/{event_id}/lock", headers=auth_headers(auth_token))
    response = client.post(f"/event/{event_id}/lock", headers=auth_headers(auth_token))
    assert response.status_code == 423


def test_unlock_event(client, auth_token):
    event_id = client.post("/event", json=EVENT_PAYLOAD, headers=auth_headers(auth_token)).json()["event_id"]
    client.post(f"/event/{event_id}/lock", headers=auth_headers(auth_token))
    response = client.post(f"/event/{event_id}/unlock", headers=auth_headers(auth_token))
    assert response.status_code == 200
    data = response.json()
    assert data["is_locked"] is False
    assert data["locked_by"] is None


@pytest.mark.asyncio
async def test_unlock_event_wrong_user(client, auth_token, mongo_client):
    event_id = client.post("/event", json=EVENT_PAYLOAD, headers=auth_headers(auth_token)).json()["event_id"]
    client.post(f"/event/{event_id}/lock", headers=auth_headers(auth_token))
    collection = await mongo_client.get_collection("axes", "events")
    await collection.update_one({"event_id": event_id}, {"$set": {"locked_by": "another_user"}})
    response = client.post(f"/event/{event_id}/unlock", headers=auth_headers(auth_token))
    assert response.status_code == 403


def test_lock_event_not_found(client, auth_token):
    response = client.post("/event/nonexistent-event-id/lock", headers=auth_headers(auth_token))
    assert response.status_code == 404


def test_unlock_event_not_found(client, auth_token):
    response = client.post("/event/nonexistent-event-id/unlock", headers=auth_headers(auth_token))
    assert response.status_code == 404


def test_finish_event(client, auth_token):
    event_id = client.post("/event", json=EVENT_PAYLOAD, headers=auth_headers(auth_token)).json()["event_id"]
    response = client.post(f"/event/{event_id}/finish", headers=auth_headers(auth_token))
    assert response.status_code == 200
    data = response.json()
    assert data["is_finished"] is True
    assert data["finished_at"] is not None


def test_finish_event_already_finished(client, auth_token):
    event_id = client.post("/event", json=EVENT_PAYLOAD, headers=auth_headers(auth_token)).json()["event_id"]
    client.post(f"/event/{event_id}/finish", headers=auth_headers(auth_token))
    response = client.post(f"/event/{event_id}/finish", headers=auth_headers(auth_token))
    assert response.status_code == 423


def test_finish_event_not_found(client, auth_token):
    response = client.post("/event/nonexistent-event-id/finish", headers=auth_headers(auth_token))
    assert response.status_code == 404


def test_delete_event(client, auth_token):
    event_id = client.post("/event", json=EVENT_PAYLOAD, headers=auth_headers(auth_token)).json()["event_id"]
    response = client.delete(f"/event/{event_id}", headers=auth_headers(auth_token))
    assert response.status_code == 204
    assert client.get(f"/event/{event_id}").status_code == 404


def test_delete_event_not_found(client, auth_token):
    response = client.delete("/event/nonexistent-event-id", headers=auth_headers(auth_token))
    assert response.status_code == 404


def test_delete_event_unauthenticated(client, auth_token):
    event_id = client.post("/event", json=EVENT_PAYLOAD, headers=auth_headers(auth_token)).json()["event_id"]
    response = client.delete(f"/event/{event_id}")
    assert response.status_code == 401
