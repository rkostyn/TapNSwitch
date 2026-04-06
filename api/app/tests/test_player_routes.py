PLAYER_PAYLOAD = {"player_name": "Test Player Alpha"}


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_player(client, auth_token):
    response = client.post("/player", json=PLAYER_PAYLOAD, headers=auth_headers(auth_token))
    assert response.status_code == 200
    data = response.json()
    assert data["player_id"]
    assert data["player_name"] == PLAYER_PAYLOAD["player_name"]
    assert data["created_at"]


def test_create_player_unauthenticated(client):
    response = client.post("/player", json=PLAYER_PAYLOAD)
    assert response.status_code == 401


def test_create_player_with_user_id(client, auth_token):
    payload = {"player_name": "Player With User", "user_id": "some-user-id"}
    response = client.post("/player", json=payload, headers=auth_headers(auth_token))
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "some-user-id"


def test_get_players(client, auth_token):
    client.post("/player", json={"player_name": "List Test Player"}, headers=auth_headers(auth_token))
    response = client.get("/player")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_get_player(client, auth_token):
    player_id = client.post("/player", json={"player_name": "Get By ID Player"}, headers=auth_headers(auth_token)).json()["player_id"]
    response = client.get(f"/player/{player_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["player_id"] == player_id
    assert data["player_name"] == "Get By ID Player"


def test_get_player_not_found(client):
    response = client.get("/player/nonexistent-player-id")
    assert response.status_code == 404


def test_delete_player(client, auth_token):
    player_id = client.post("/player", json={"player_name": "Player To Delete"}, headers=auth_headers(auth_token)).json()["player_id"]
    response = client.delete(f"/player/{player_id}", headers=auth_headers(auth_token))
    assert response.status_code == 204
    # Verify it's gone
    assert client.get(f"/player/{player_id}").status_code == 404


def test_delete_player_not_found(client, auth_token):
    response = client.delete("/player/nonexistent-player-id", headers=auth_headers(auth_token))
    assert response.status_code == 404


def test_delete_player_unauthenticated(client, auth_token):
    player_id = client.post("/player", json={"player_name": "Protected Player"}, headers=auth_headers(auth_token)).json()["player_id"]
    response = client.delete(f"/player/{player_id}")
    assert response.status_code == 401
