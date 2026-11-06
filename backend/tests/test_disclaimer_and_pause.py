"""Issues #3 and #4: Pause All state and the legal disclaimer."""

import pytest
from rest_framework.test import APIClient

from accounts.disclaimer import DISCLAIMER_VERSION
from accounts.gates import disclaimer_accepted, disclaimer_required
from accounts.models import User

PAUSE = "/api/auth/pause/"
DISCLAIMER = "/api/auth/disclaimer/"


@pytest.fixture
def seeker(db):
    return User.objects.create_user(username="s", email="s@example.com", password="Pass12345!")


@pytest.fixture
def client(seeker):
    api = APIClient()
    api.force_authenticate(seeker)
    return api


# ----------------------------------------------------------------- Pause All (#3)


@pytest.mark.django_db
def test_pause_state_can_be_read_and_changed(client, seeker):
    assert client.get(PAUSE).data == {"automation_paused": False}
    assert client.post(PAUSE, {"paused": True}, format="json").data == {"automation_paused": True}
    assert client.get(PAUSE).data == {"automation_paused": True}
    seeker.refresh_from_db()
    assert seeker.automation_paused is True
    assert client.post(PAUSE, {"paused": False}, format="json").data == {"automation_paused": False}
    assert client.get(PAUSE).data == {"automation_paused": False}


@pytest.mark.django_db
def test_posting_with_no_body_pauses_everything(client):
    assert client.post(PAUSE, {}, format="json").data == {"automation_paused": True}


@pytest.mark.django_db
def test_pause_belongs_to_the_logged_in_user(client, seeker):
    other = User.objects.create_user(username="o", email="o@example.com", password="Pass12345!")
    client.post(PAUSE, {"paused": True}, format="json")
    other.refresh_from_db()
    assert other.automation_paused is False


@pytest.mark.django_db
def test_pause_needs_a_login():
    assert APIClient().get(PAUSE).status_code == 401
    assert APIClient().post(PAUSE, {}, format="json").status_code == 401


# ------------------------------------------------------------- disclaimer (#4)


@pytest.mark.django_db
def test_disclaimer_is_shown_and_starts_unaccepted(client):
    response = client.get(DISCLAIMER)
    assert response.status_code == 200
    assert response.data["version"] == DISCLAIMER_VERSION
    assert "not liable" in response.data["text"]
    assert response.data["accepted"] is False
    assert response.data["accepted_at"] is None


@pytest.mark.django_db
@pytest.mark.parametrize("body", [{}, {"accept": False}, {"accept": "no"}])
def test_accepting_needs_an_explicit_yes(client, seeker, body):
    assert client.post(DISCLAIMER, body, format="json").status_code == 400
    seeker.refresh_from_db()
    assert seeker.disclaimer_accepted_at is None


@pytest.mark.django_db
def test_accepting_records_the_time_and_version(client, seeker):
    response = client.post(DISCLAIMER, {"accept": True}, format="json")
    assert response.status_code == 200
    assert response.data["accepted"] is True
    assert response.data["accepted_at"] is not None
    seeker.refresh_from_db()
    assert seeker.disclaimer_version == DISCLAIMER_VERSION
    assert client.get(DISCLAIMER).data["accepted"] is True


@pytest.mark.django_db
def test_accepting_twice_keeps_the_first_time(client, seeker):
    client.post(DISCLAIMER, {"accept": True}, format="json")
    seeker.refresh_from_db()
    first = seeker.disclaimer_accepted_at
    client.post(DISCLAIMER, {"accept": "true"}, format="json")
    seeker.refresh_from_db()
    assert seeker.disclaimer_accepted_at == first


@pytest.mark.django_db
def test_an_older_disclaimer_version_must_be_accepted_again(client, seeker):
    client.post(DISCLAIMER, {"accept": True}, format="json")
    seeker.disclaimer_version = "0.1"
    seeker.save()
    assert client.get(DISCLAIMER).data["accepted"] is False
    assert client.get(DISCLAIMER).data["accepted_at"] is None
    client.post(DISCLAIMER, {"accept": True}, format="json")
    assert client.get(DISCLAIMER).data["accepted"] is True


@pytest.mark.django_db
def test_disclaimer_needs_a_login():
    assert APIClient().get(DISCLAIMER).status_code == 401


# ------------------------------------------------------------------------ gate


@pytest.mark.django_db
def test_gate_is_off_by_default_under_pytest_so_older_tests_are_unaffected(seeker):
    assert disclaimer_required() is False
    assert disclaimer_accepted(seeker) is True


@pytest.mark.django_db
def test_gate_blocks_until_the_disclaimer_is_accepted(settings, client, seeker):
    settings.REQUIRE_DISCLAIMER = True
    assert disclaimer_required() is True
    assert disclaimer_accepted(seeker) is False
    assert client.get(DISCLAIMER).data["required"] is True
    client.post(DISCLAIMER, {"accept": True}, format="json")
    seeker.refresh_from_db()
    assert disclaimer_accepted(seeker) is True


def test_gate_can_be_forced_off(settings):
    settings.REQUIRE_DISCLAIMER = False
    assert disclaimer_required() is False
