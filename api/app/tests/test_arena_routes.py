def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_event(client, auth_token, players=None, **extra):
    payload = {"event_name": "Tourney", "players": players or ["Alice", "Bob", "Carol", "Dan"]}
    payload.update(extra)
    return client.post("/event", json=payload, headers=auth_headers(auth_token)).json()


def test_create_event_gets_default_arenas(client, auth_token):
    event = _create_event(client, auth_token)
    assert event["arena_ids"]
    assert "blue-left" in event["arena_ids"]


def test_update_event_arenas(client, auth_token):
    event = _create_event(client, auth_token)
    event_id = event["event_id"]
    response = client.put(
        f"/event/{event_id}/arenas",
        json={"arena_ids": ["blue-left"]},
        headers=auth_headers(auth_token),
    )
    assert response.status_code == 200
    assert response.json()["arena_ids"] == ["blue-left"]


def test_swiss_matches_assign_arenas(client, auth_token):
    event = _create_event(client, auth_token)
    event_id = event["event_id"]
    matches = client.post(
        f"/event/{event_id}/swiss/generate",
        headers=auth_headers(auth_token),
    ).json()
    arena_ids = set(event["arena_ids"])
    assigned = {m["arena_id"] for m in matches if m.get("arena_id")}
    assert assigned
    assert assigned.issubset(arena_ids)


def test_update_match_arena(client, auth_token):
    event = _create_event(client, auth_token)
    event_id = event["event_id"]
    matches = client.post(
        f"/event/{event_id}/swiss/generate",
        headers=auth_headers(auth_token),
    ).json()
    match_id = matches[0]["match_id"]
    target = event["arena_ids"][0]
    response = client.patch(
        f"/match/{match_id}/arena",
        json={"arena_id": target},
        headers=auth_headers(auth_token),
    )
    assert response.status_code == 200
    assert response.json()["arena_id"] == target


def test_update_match_arena_not_on_event(client, auth_token):
    event = _create_event(client, auth_token)
    event_id = event["event_id"]
    client.put(
        f"/event/{event_id}/arenas",
        json={"arena_ids": ["blue-left"]},
        headers=auth_headers(auth_token),
    )
    matches = client.post(
        f"/event/{event_id}/swiss/generate",
        headers=auth_headers(auth_token),
    ).json()
    response = client.patch(
        f"/match/{matches[0]['match_id']}/arena",
        json={"arena_id": "black-right"},
        headers=auth_headers(auth_token),
    )
    assert response.status_code == 400
