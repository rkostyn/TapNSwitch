def test_startup_check(client):
    response = client.get("/startup-check")
    assert response.status_code == 200
    assert response.json() == {"message": "ok"}


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"message": "ok"}
