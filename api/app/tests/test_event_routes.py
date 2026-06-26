import pytest

EVENT_PAYLOAD = {"event_name": "Test Event", "players": ["Alice", "Bob"]}


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_event(client, auth_token):
    response = client.post("/event", json=EVENT_PAYLOAD, headers=auth_headers(auth_token))
    assert response.status_code == 200
    data = response.json()
    assert data["event_id"]
    assert data["event_name"] == EVENT_PAYLOAD["event_name"]
    assert data["players"] == EVENT_PAYLOAD["players"]
    assert data["created_by"] == "testuser"
    assert data["is_locked"] is False
    assert data["locked_by"] is None


def test_list_events(client, auth_token):
    create_resp = client.post("/event", json=EVENT_PAYLOAD, headers=auth_headers(auth_token))
    event_id = create_resp.json()["event_id"]
    response = client.get("/event", headers=auth_headers(auth_token))
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    created = next(e for e in data if e["event_id"] == event_id)
    assert created["created_by"] == "testuser"


def test_list_events_unauthenticated(client):
    response = client.get("/event")
    assert response.status_code == 401


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


def test_create_event_missing_event_name(client, auth_token):
    response = client.post("/event", json={"players": ["Alice"]}, headers=auth_headers(auth_token))
    assert response.status_code == 422


def test_create_event_empty_event_name(client, auth_token):
    response = client.post("/event", json={"event_name": "", "players": ["Alice"]}, headers=auth_headers(auth_token))
    assert response.status_code == 422


def test_create_event_missing_players(client, auth_token):
    response = client.post("/event", json={"event_name": "Test"}, headers=auth_headers(auth_token))
    assert response.status_code == 422


def test_create_event_empty_players(client, auth_token):
    response = client.post("/event", json={"event_name": "Test", "players": []}, headers=auth_headers(auth_token))
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Player management
# ---------------------------------------------------------------------------

def _create_event(client, auth_token, players=None, **extra):
    payload = {"event_name": "Tourney", "players": players or ["Alice", "Bob", "Carol", "Dan"]}
    payload.update(extra)
    return client.post("/event", json=payload, headers=auth_headers(auth_token)).json()


def test_add_player(client, auth_token):
    event = _create_event(client, auth_token)
    response = client.post(
        f"/event/{event['event_id']}/player", json={"player_name": "Eve"}, headers=auth_headers(auth_token)
    )
    assert response.status_code == 200
    assert "Eve" in response.json()["players"]


def test_add_player_duplicate(client, auth_token):
    event = _create_event(client, auth_token)
    response = client.post(
        f"/event/{event['event_id']}/player", json={"player_name": "Alice"}, headers=auth_headers(auth_token)
    )
    assert response.status_code == 409


def test_add_player_event_not_found(client, auth_token):
    response = client.post(
        "/event/nonexistent/player", json={"player_name": "Eve"}, headers=auth_headers(auth_token)
    )
    assert response.status_code == 404


def test_add_player_finished_event(client, auth_token):
    event = _create_event(client, auth_token)
    client.post(f"/event/{event['event_id']}/finish", headers=auth_headers(auth_token))
    response = client.post(
        f"/event/{event['event_id']}/player", json={"player_name": "Eve"}, headers=auth_headers(auth_token)
    )
    assert response.status_code == 423


def test_remove_player(client, auth_token):
    event = _create_event(client, auth_token)
    response = client.delete(
        f"/event/{event['event_id']}/player/Bob", headers=auth_headers(auth_token)
    )
    assert response.status_code == 200
    assert "Bob" not in response.json()["players"]


def test_remove_player_also_clears_late(client, auth_token):
    event = _create_event(client, auth_token)
    event_id = event["event_id"]
    client.put(f"/event/{event_id}/player/Bob/late", json={"late": True}, headers=auth_headers(auth_token))
    response = client.delete(f"/event/{event_id}/player/Bob", headers=auth_headers(auth_token))
    assert response.status_code == 200
    assert "Bob" not in response.json()["late_players"]


def test_remove_unknown_player(client, auth_token):
    event = _create_event(client, auth_token)
    response = client.delete(
        f"/event/{event['event_id']}/player/Nobody", headers=auth_headers(auth_token)
    )
    assert response.status_code == 404


def test_remove_player_event_not_found(client, auth_token):
    response = client.delete("/event/nonexistent/player/Bob", headers=auth_headers(auth_token))
    assert response.status_code == 404


def test_remove_player_finished_event(client, auth_token):
    event = _create_event(client, auth_token)
    client.post(f"/event/{event['event_id']}/finish", headers=auth_headers(auth_token))
    response = client.delete(
        f"/event/{event['event_id']}/player/Bob", headers=auth_headers(auth_token)
    )
    assert response.status_code == 423


def test_mark_player_late_and_back(client, auth_token):
    event = _create_event(client, auth_token)
    event_id = event["event_id"]
    response = client.put(
        f"/event/{event_id}/player/Bob/late", json={"late": True}, headers=auth_headers(auth_token)
    )
    assert response.status_code == 200
    assert response.json()["late_players"] == ["Bob"]
    response = client.put(
        f"/event/{event_id}/player/Bob/late", json={"late": False}, headers=auth_headers(auth_token)
    )
    assert response.status_code == 200
    assert response.json()["late_players"] == []


def test_mark_unknown_player_late(client, auth_token):
    event = _create_event(client, auth_token)
    response = client.put(
        f"/event/{event['event_id']}/player/Nobody/late", json={"late": True}, headers=auth_headers(auth_token)
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Swiss config + generation
# ---------------------------------------------------------------------------

def test_event_defaults_swiss_config(client, auth_token):
    event = _create_event(client, auth_token)
    assert event["swiss_matches_per_player"] == 2
    assert event["swiss_rounds_per_match"] == 2


def test_update_swiss_config(client, auth_token):
    event = _create_event(client, auth_token)
    response = client.put(
        f"/event/{event['event_id']}/swiss-config",
        json={"swiss_matches_per_player": 3, "swiss_rounds_per_match": 1},
        headers=auth_headers(auth_token),
    )
    assert response.status_code == 200
    assert response.json()["swiss_matches_per_player"] == 3
    assert response.json()["swiss_rounds_per_match"] == 1


def test_generate_swiss_matches(client, auth_token):
    event = _create_event(client, auth_token)
    response = client.post(f"/event/{event['event_id']}/swiss/generate", headers=auth_headers(auth_token))
    assert response.status_code == 200
    matches = response.json()
    assert len(matches) == 4  # 4 players x 2 matches each / 2 players per match
    counts = {}
    for m in matches:
        assert m["match_type"] == "swiss"
        assert m["rounds_per_match"] == 2
        counts[m["player_1_id"]] = counts.get(m["player_1_id"], 0) + 1
        counts[m["player_2_id"]] = counts.get(m["player_2_id"], 0) + 1
    assert all(c == 2 for c in counts.values())


def test_regenerate_swiss_when_unplayed(client, auth_token):
    # Adding a player and regenerating before any throws rebuilds the schedule
    event = _create_event(client, auth_token)
    event_id = event["event_id"]
    client.post(f"/event/{event_id}/swiss/generate", headers=auth_headers(auth_token))
    client.post(f"/event/{event_id}/player", json={"player_name": "Eve"}, headers=auth_headers(auth_token))
    response = client.post(f"/event/{event_id}/swiss/generate", headers=auth_headers(auth_token))
    assert response.status_code == 200
    players_in_matches = {p for m in response.json() for p in (m["player_1_id"], m["player_2_id"])}
    assert "Eve" in players_in_matches


def test_add_player_after_scores_appends_matches(client, auth_token):
    # A late entrant can join even after a match is scored: their matches are
    # appended and the already-scored matches are left untouched.
    event = _create_event(client, auth_token)
    event_id = event["event_id"]
    matches = client.post(f"/event/{event_id}/swiss/generate", headers=auth_headers(auth_token)).json()
    _submit_round_throws(client, auth_token, matches[0], 1, 5, 1)
    scored_id = matches[0]["match_id"]

    client.post(f"/event/{event_id}/player", json={"player_name": "Eve"}, headers=auth_headers(auth_token))
    response = client.post(f"/event/{event_id}/swiss/generate", headers=auth_headers(auth_token))
    assert response.status_code == 200
    all_matches = response.json()

    # Original scored match is still present and unchanged
    assert any(m["match_id"] == scored_id for m in all_matches)
    # Eve now has her full quota of matches
    eve_matches = [m for m in all_matches if "Eve" in (m["player_1_id"], m["player_2_id"])]
    assert len(eve_matches) == 2


def test_regenerate_swiss_after_scores_without_new_players_is_noop(client, auth_token):
    event = _create_event(client, auth_token, players=["Alice", "Bob"])
    event_id = event["event_id"]
    matches = client.post(f"/event/{event_id}/swiss/generate", headers=auth_headers(auth_token)).json()
    _submit_round_throws(client, auth_token, matches[0], 1, 5, 1)
    response = client.post(f"/event/{event_id}/swiss/generate", headers=auth_headers(auth_token))
    assert response.status_code == 200
    assert len(response.json()) == len(matches)


def test_swiss_config_editable_until_scores(client, auth_token):
    # Config stays editable after generation, as long as no throws are recorded
    event = _create_event(client, auth_token)
    client.post(f"/event/{event['event_id']}/swiss/generate", headers=auth_headers(auth_token))
    response = client.put(
        f"/event/{event['event_id']}/swiss-config",
        json={"swiss_matches_per_player": 3, "swiss_rounds_per_match": 1},
        headers=auth_headers(auth_token),
    )
    assert response.status_code == 200


def test_swiss_config_locked_after_scores(client, auth_token):
    event = _create_event(client, auth_token, players=["Alice", "Bob"])
    event_id = event["event_id"]
    matches = client.post(f"/event/{event_id}/swiss/generate", headers=auth_headers(auth_token)).json()
    _submit_round_throws(client, auth_token, matches[0], 1, 5, 1)
    response = client.put(
        f"/event/{event_id}/swiss-config",
        json={"swiss_matches_per_player": 3, "swiss_rounds_per_match": 1},
        headers=auth_headers(auth_token),
    )
    assert response.status_code == 409


def test_generate_swiss_odd_imbalance_adds_ghost(client, auth_token):
    # 5 players x 1 match each is odd, so one player gets a ghost match
    event = _create_event(client, auth_token, players=["Alice", "Bob", "Carol", "Dan", "Eve"])
    event_id = event["event_id"]
    client.put(
        f"/event/{event_id}/swiss-config",
        json={"swiss_matches_per_player": 1, "swiss_rounds_per_match": 2},
        headers=auth_headers(auth_token),
    )
    matches = client.post(f"/event/{event_id}/swiss/generate", headers=auth_headers(auth_token)).json()
    ghost_matches = [m for m in matches if m["player_2_id"] == "__ghost__"]
    assert len(ghost_matches) == 1
    # Everyone still gets exactly one match
    counts = {}
    for m in matches:
        for p in (m["player_1_id"], m["player_2_id"]):
            if p != "__ghost__":
                counts[p] = counts.get(p, 0) + 1
    assert all(c == 1 for c in counts.values())
    assert len(counts) == 5


def test_generate_swiss_late_players_last(client, auth_token):
    event = _create_event(client, auth_token)
    event_id = event["event_id"]
    client.put(f"/event/{event_id}/player/Dan/late", json={"late": True}, headers=auth_headers(auth_token))
    matches = client.post(f"/event/{event_id}/swiss/generate", headers=auth_headers(auth_token)).json()
    involves_late = ["Dan" in (m["player_1_id"], m["player_2_id"]) for m in matches]
    first_late = involves_late.index(True)
    assert all(involves_late[first_late:])


# ---------------------------------------------------------------------------
# Swiss scores / standings / bracket
# ---------------------------------------------------------------------------

def _submit_round_throws(client, auth_token, match, round_seq, p1_points, p2_points):
    round_resp = client.post(
        "/round",
        json={
            "match_id": match["match_id"],
            "player_1_id": match["player_1_id"],
            "player_2_id": match["player_2_id"],
            "sequence": round_seq,
        },
        headers=auth_headers(auth_token),
    )
    assert round_resp.status_code == 200
    round_id = round_resp.json()["round_id"]
    for player, points in ((match["player_1_id"], p1_points), (match["player_2_id"], p2_points)):
        resp = client.post(
            "/throw/submit",
            json={
                "player_id": player,
                "round_id": round_id,
                "match_id": match["match_id"],
                "event_id": match["event_id"],
                "points": points,
            },
            headers=auth_headers(auth_token),
        )
        assert resp.status_code == 200


def test_swiss_scores_and_standings(client, auth_token):
    event = _create_event(client, auth_token, players=["Alice", "Bob"])
    event_id = event["event_id"]
    matches = client.post(f"/event/{event_id}/swiss/generate", headers=auth_headers(auth_token)).json()
    # Alice dominates both matches
    for match in matches:
        a_first = match["player_1_id"] == "Alice"
        _submit_round_throws(client, auth_token, match, 1, 5 if a_first else 1, 1 if a_first else 5)

    response = client.post(f"/event/{event_id}/swiss/scores", headers=auth_headers(auth_token))
    assert response.status_code == 200
    standings = response.json()
    assert standings[0]["player"] == "Alice"
    assert standings[0]["points"] == 10
    assert standings[0]["rounds_won"] == 2
    assert standings[1]["player"] == "Bob"

    # Stored standings are retrievable
    response = client.get(f"/event/{event_id}/standings")
    assert response.status_code == 200
    assert response.json()[0]["player"] == "Alice"


def test_standings_before_scores_404(client, auth_token):
    event = _create_event(client, auth_token)
    response = client.get(f"/event/{event['event_id']}/standings")
    assert response.status_code == 404


def test_swiss_scores_without_matches_conflicts(client, auth_token):
    event = _create_event(client, auth_token)
    response = client.post(f"/event/{event['event_id']}/swiss/scores", headers=auth_headers(auth_token))
    assert response.status_code == 409


def test_generate_bracket_requires_standings(client, auth_token):
    event = _create_event(client, auth_token)
    response = client.post(
        f"/event/{event['event_id']}/bracket/generate", json={}, headers=auth_headers(auth_token)
    )
    assert response.status_code == 409


def _event_through_swiss(client, auth_token, players):
    event = _create_event(client, auth_token, players=players)
    event_id = event["event_id"]
    matches = client.post(f"/event/{event_id}/swiss/generate", headers=auth_headers(auth_token)).json()
    # Deterministic scoring: alphabetical order wins
    for match in matches:
        p1_wins = match["player_1_id"] < match["player_2_id"]
        _submit_round_throws(client, auth_token, match, 1, 5 if p1_wins else 1, 1 if p1_wins else 5)
    client.post(f"/event/{event_id}/swiss/scores", headers=auth_headers(auth_token))
    return event_id


def test_generate_bracket_default_three_rounds(client, auth_token):
    event_id = _event_through_swiss(client, auth_token, ["Alice", "Bob", "Carol", "Dan"])
    response = client.post(f"/event/{event_id}/bracket/generate", json={}, headers=auth_headers(auth_token))
    assert response.status_code == 200
    matches = response.json()
    assert len(matches) == 3
    assert all(m["rounds_per_match"] == 3 for m in matches)
    assert all(m["match_type"] == "bracket" for m in matches)

    bracket = client.get(f"/event/{event_id}/bracket").json()
    assert len(bracket) == 3


def test_generate_bracket_custom_rounds(client, auth_token):
    event_id = _event_through_swiss(client, auth_token, ["Alice", "Bob"])
    response = client.post(
        f"/event/{event_id}/bracket/generate", json={"rounds_per_match": 1}, headers=auth_headers(auth_token)
    )
    assert response.status_code == 200
    assert all(m["rounds_per_match"] == 1 for m in response.json())


def test_generate_bracket_twice_conflicts(client, auth_token):
    event_id = _event_through_swiss(client, auth_token, ["Alice", "Bob"])
    client.post(f"/event/{event_id}/bracket/generate", json={}, headers=auth_headers(auth_token))
    response = client.post(f"/event/{event_id}/bracket/generate", json={}, headers=auth_headers(auth_token))
    assert response.status_code == 409


def test_bracket_winner_advances(client, auth_token):
    event_id = _event_through_swiss(client, auth_token, ["Alice", "Bob", "Carol", "Dan"])
    bracket = client.post(f"/event/{event_id}/bracket/generate", json={}, headers=auth_headers(auth_token)).json()
    semi = next(m for m in bracket if m["bracket_round"] == 1 and m["bracket_slot"] == 0)
    final = next(m for m in bracket if m["bracket_round"] == 2)

    _submit_round_throws(client, auth_token, semi, 1, 7, 0)
    response = client.post(f"/match/{semi['match_id']}/finish", headers=auth_headers(auth_token))
    assert response.status_code == 200
    assert response.json()["winner_id"] == semi["player_1_id"]

    updated_final = client.get(f"/match/{final['match_id']}").json()
    assert updated_final["player_1_id"] == semi["player_1_id"]
