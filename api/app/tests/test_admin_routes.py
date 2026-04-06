"""
Tests for the admin routes.

Admin sessions use a cookie with secure=True, so TestClient (http://) won't
automatically store/replay them.  Instead we seed known tokens directly into
the shared FakeRedisClient and pass them explicitly via `cookies=`.
"""
import base64
import hashlib
import json
import time

import bcrypt

# Import the shared fake instances seeded in conftest so we can manipulate
# them at module level (before any fixtures run).
from app.tests.conftest import _fake_mongo, _fake_redis

# ---------------------------------------------------------------------------
# Module-level setup: seed an admin user + a known session token
# ---------------------------------------------------------------------------

_ADMIN_USERNAME = "adminuser"
_ADMIN_PASSWORD = "adminpassword"
_ADMIN_TOKEN = "test-admin-session-token-fixed"
_LOGOUT_TOKEN = "test-admin-logout-token-fixed"


def _seed_admin():
    users = _fake_mongo._get_or_create("axes", "users")
    # Avoid double-seeding across test re-imports
    if any(u.get("user_name") == _ADMIN_USERNAME for u in users._docs):
        return
    password_hash = bcrypt.hashpw(_ADMIN_PASSWORD.encode(), bcrypt.gensalt()).decode()
    from datetime import UTC, datetime
    users._docs.append({
        "user_id": "admin-user-id-fixed",
        "user_name": _ADMIN_USERNAME,
        "email": "admin@test.com",
        "password_hash": password_hash,
        "created_at": datetime.now(UTC),
        "is_admin": True,
    })


def _seed_admin_token(token: str):
    h = hashlib.sha256(token.encode()).hexdigest()
    key = f"auth:admin_token:{h}"
    _fake_redis._store[key] = json.dumps(_ADMIN_USERNAME)
    _fake_redis._expires[key] = time.monotonic() + 86400


_seed_admin()
_seed_admin_token(_ADMIN_TOKEN)
_seed_admin_token(_LOGOUT_TOKEN)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def admin_cookies():
    return {"admin_session": _ADMIN_TOKEN}


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


# ---------------------------------------------------------------------------
# Login page
# ---------------------------------------------------------------------------

def test_get_login_page(client):
    response = client.get("/admin/login")
    assert response.status_code == 200
    assert b"login" in response.content.lower()


# ---------------------------------------------------------------------------
# POST /admin/login — error cases (returns 200 with error template)
# ---------------------------------------------------------------------------

def test_post_login_invalid_base64(client):
    response = client.post("/admin/login", data={"credentials": "!!!not-base64!!!"})
    assert response.status_code == 200
    assert b"invalid" in response.content.lower()


def test_post_login_no_colon_in_decoded(client):
    # Valid base64 but no colon separator
    response = client.post("/admin/login", data={"credentials": b64("usernameonly")})
    assert response.status_code == 200
    assert b"invalid" in response.content.lower()


def test_post_login_wrong_password(client):
    response = client.post("/admin/login", data={"credentials": b64(f"{_ADMIN_USERNAME}:wrongpassword")})
    assert response.status_code == 200
    assert b"invalid" in response.content.lower()


def test_post_login_non_admin_user(client):
    # "testuser" is pre-seeded in conftest with is_admin=False
    response = client.post("/admin/login", data={"credentials": b64("testuser:testpassword")})
    assert response.status_code == 200
    assert b"invalid" in response.content.lower()


def test_post_login_unknown_user(client):
    response = client.post("/admin/login", data={"credentials": b64("nobody:somepassword")})
    assert response.status_code == 200
    assert b"invalid" in response.content.lower()


# ---------------------------------------------------------------------------
# POST /admin/login — success (check redirect + Set-Cookie header)
# ---------------------------------------------------------------------------

def test_post_login_admin_success(client):
    response = client.post(
        "/admin/login",
        data={"credentials": b64(f"{_ADMIN_USERNAME}:{_ADMIN_PASSWORD}")},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"].endswith("/admin/")
    assert "admin_session" in response.headers.get("set-cookie", "")


# ---------------------------------------------------------------------------
# GET /admin/ — index
# ---------------------------------------------------------------------------

def test_get_admin_index_unauthenticated(client):
    response = client.get("/admin/", follow_redirects=False)
    assert response.status_code == 302
    assert "login" in response.headers["location"]


def test_get_admin_index_authenticated(client):
    response = client.get("/admin/", cookies=admin_cookies())
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /admin/logout
# ---------------------------------------------------------------------------

def test_get_admin_logout_clears_session(client):
    # Use the dedicated logout token so the main _ADMIN_TOKEN is unaffected
    response = client.get(
        "/admin/logout",
        cookies={"admin_session": _LOGOUT_TOKEN},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "login" in response.headers["location"]
    # The token should now be gone from Redis
    h = hashlib.sha256(_LOGOUT_TOKEN.encode()).hexdigest()
    assert f"auth:admin_token:{h}" not in _fake_redis._store


# ---------------------------------------------------------------------------
# PATCH /admin/{collection}/{doc_id}
# ---------------------------------------------------------------------------

def test_patch_admin_doc_unauthenticated(client, auth_token):
    event_id = client.post("/event", json={"venue_id": "patch_unauth_venue"}, headers=auth_headers(auth_token)).json()["event_id"]
    response = client.patch(f"/admin/events/{event_id}", json={"venue_id": "x"})
    assert response.status_code == 401


def test_patch_admin_doc_unknown_collection(client):
    response = client.patch("/admin/foobar/some-id", json={"field": "val"}, cookies=admin_cookies())
    assert response.status_code == 404
    assert "unknown collection" in response.json()["detail"].lower()


def test_patch_admin_doc_not_found(client):
    response = client.patch("/admin/events/nonexistent-doc-id", json={"venue_id": "x"}, cookies=admin_cookies())
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_patch_admin_doc_empty_body_after_denylist_strip(client, auth_token):
    event_id = client.post("/event", json={"venue_id": "strip_venue"}, headers=auth_headers(auth_token)).json()["event_id"]
    # Send only denylist fields — should result in 400 after stripping
    response = client.patch(
        f"/admin/events/{event_id}",
        json={"password_hash": "x", "is_admin": True, "_id": "y"},
        cookies=admin_cookies(),
    )
    assert response.status_code == 400


def test_patch_admin_doc_success(client, auth_token):
    event_id = client.post("/event", json={"venue_id": "original_venue"}, headers=auth_headers(auth_token)).json()["event_id"]
    response = client.patch(
        f"/admin/events/{event_id}",
        json={"venue_id": "patched_venue"},
        cookies=admin_cookies(),
    )
    assert response.status_code == 200
    assert response.json()["updated"] == 1
    # Verify change persisted
    assert client.get(f"/event/{event_id}").json()["venue_id"] == "patched_venue"


def test_patch_admin_doc_strips_id_field(client, auth_token):
    event_id = client.post("/event", json={"venue_id": "id_strip_venue"}, headers=auth_headers(auth_token)).json()["event_id"]
    # event_id is the collection's id field — should be stripped, rest applied
    response = client.patch(
        f"/admin/events/{event_id}",
        json={"event_id": "fake-id", "venue_id": "ok_venue"},
        cookies=admin_cookies(),
    )
    assert response.status_code == 200
    # event_id must remain unchanged
    data = client.get(f"/event/{event_id}").json()
    assert data["event_id"] == event_id
    assert data["venue_id"] == "ok_venue"


# ---------------------------------------------------------------------------
# DELETE /admin/{collection}/{doc_id}
# ---------------------------------------------------------------------------

def test_delete_admin_doc_unauthenticated(client, auth_token):
    event_id = client.post("/event", json={"venue_id": "del_unauth_venue"}, headers=auth_headers(auth_token)).json()["event_id"]
    response = client.delete(f"/admin/events/{event_id}")
    assert response.status_code == 401


def test_delete_admin_doc_unknown_collection(client):
    response = client.delete("/admin/foobar/some-id", cookies=admin_cookies())
    assert response.status_code == 404
    assert "unknown collection" in response.json()["detail"].lower()


def test_delete_admin_doc_not_found(client):
    response = client.delete("/admin/events/nonexistent-doc-id", cookies=admin_cookies())
    assert response.status_code == 404


def test_delete_admin_doc_success(client, auth_token):
    event_id = client.post("/event", json={"venue_id": "admin_del_venue"}, headers=auth_headers(auth_token)).json()["event_id"]
    response = client.delete(f"/admin/events/{event_id}", cookies=admin_cookies())
    assert response.status_code == 204
    assert client.get(f"/event/{event_id}").status_code == 404


# ---------------------------------------------------------------------------
# GET /admin/{collection}/{doc_id} — detail page
# ---------------------------------------------------------------------------

def test_get_admin_detail_unauthenticated(client, auth_token):
    event_id = client.post("/event", json={"venue_id": "detail_unauth"}, headers=auth_headers(auth_token)).json()["event_id"]
    response = client.get(f"/admin/events/{event_id}", follow_redirects=False)
    assert response.status_code == 302
    assert "login" in response.headers["location"]


def test_get_admin_detail_unknown_collection(client):
    response = client.get("/admin/foobar/some-id", cookies=admin_cookies())
    assert response.status_code == 404


def test_get_admin_detail_not_found(client):
    response = client.get("/admin/events/nonexistent-doc-id", cookies=admin_cookies())
    assert response.status_code == 404


def test_get_admin_detail_success(client, auth_token):
    event_id = client.post("/event", json={"venue_id": "detail_venue"}, headers=auth_headers(auth_token)).json()["event_id"]
    response = client.get(f"/admin/events/{event_id}", cookies=admin_cookies())
    assert response.status_code == 200
    assert event_id.encode() in response.content


def test_get_admin_detail_user_excludes_password_hash(client):
    # The admin detail for users must not expose password_hash
    response = client.get("/admin/users/test-user-id-fixed", cookies=admin_cookies())
    assert response.status_code == 200
    assert b"password_hash" not in response.content
