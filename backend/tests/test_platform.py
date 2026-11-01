import pytest


@pytest.mark.django_db
def test_health_endpoint(client):
    assert client.get("/health/").json() == {"status": "ok"}


@pytest.mark.django_db
def test_register_and_login(client):
    assert client.post("/api/auth/register/", {"email": "n@pes.edu", "password": "Str0ng!pass9"}).status_code == 201
    assert "access" in client.post("/api/auth/login/", {"email": "n@pes.edu", "password": "Str0ng!pass9"}).json()
