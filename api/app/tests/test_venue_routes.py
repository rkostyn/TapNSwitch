def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_get_venue_arenas_defaults(client, auth_token):
    response = client.get("/venue/arenas", headers=auth_headers(auth_token))
    assert response.status_code == 200
    arenas = response.json()["arenas"]
    assert len(arenas) >= 2
    assert any(a["id"] == "blue-left" for a in arenas)


def test_update_venue_arenas(client, auth_token):
    payload = {
        "arenas": [
            {"id": "blue-left", "label": "Blue - Left"},
            {"id": "black-right", "label": "Black - Right"},
            {"id": "green-center", "label": "Green - Center"},
        ]
    }
    response = client.put("/venue/arenas", json=payload, headers=auth_headers(auth_token))
    assert response.status_code == 200
    arenas = response.json()["arenas"]
    assert len(arenas) == 3
    assert arenas[2]["label"] == "Green - Center"

    get_resp = client.get("/venue/arenas", headers=auth_headers(auth_token))
    assert get_resp.json()["arenas"] == arenas


def test_venue_arenas_unauthenticated(client):
    assert client.get("/venue/arenas").status_code == 401
    assert client.put("/venue/arenas", json={"arenas": [{"id": "x", "label": "X"}]}).status_code == 401
