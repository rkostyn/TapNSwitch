def test_startup_check(client):
    response = client.get("/startup-check")
    assert response.status_code == 200
    assert response.json() == {"message": "ok"}


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"message": "ok"}


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------

def test_security_headers_present(client):
    response = client.get("/startup-check")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


# ---------------------------------------------------------------------------
# X-Request-ID middleware
# ---------------------------------------------------------------------------

def test_request_id_generated_when_absent(client):
    response = client.get("/startup-check")
    rid = response.headers.get("X-Request-ID", "")
    assert len(rid) == 36  # UUID4 format


def test_valid_request_id_echoed_back(client):
    response = client.get("/startup-check", headers={"X-Request-ID": "my-request-123"})
    assert response.headers.get("X-Request-ID") == "my-request-123"


def test_invalid_request_id_replaced(client):
    # Contains characters outside [a-zA-Z0-9\-] — should be replaced
    response = client.get("/startup-check", headers={"X-Request-ID": "bad id with spaces!!"})
    rid = response.headers.get("X-Request-ID", "")
    assert rid != "bad id with spaces!!"
    assert len(rid) == 36  # replaced with a UUID


def test_oversized_request_id_replaced(client):
    response = client.get("/startup-check", headers={"X-Request-ID": "a" * 65})
    rid = response.headers.get("X-Request-ID", "")
    assert rid != "a" * 65
    assert len(rid) == 36


# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------

def test_cors_preflight_returns_200(client):
    response = client.options(
        "/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert response.status_code == 200


def test_cors_headers_present_on_response(client):
    response = client.get(
        "/startup-check",
        headers={"Origin": "http://localhost:3000"},
    )
    assert "access-control-allow-origin" in response.headers


def test_cors_wildcard_when_no_origins_configured(client):
    # Default test environment has CORS_ORIGINS unset → falls back to "*"
    response = client.get(
        "/startup-check",
        headers={"Origin": "http://example.com"},
    )
    assert response.headers.get("access-control-allow-origin") in ("*", "http://example.com")
