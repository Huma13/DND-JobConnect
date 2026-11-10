import pytest
from rest_framework.test import APIClient

from accounts.models import User
from scheduler.models import ScheduledRun

URL = "/api/scheduler/admin/runs/"


@pytest.fixture
def admin_account(db):
    return User.objects.create_user(
        username="admin1", email="admin1@example.com", password="Pass12345!", role=User.Role.ADMIN
    )


@pytest.fixture
def seeker_account(db):
    return User.objects.create_user(
        username="seeker1", email="seeker1@example.com", password="Pass12345!"
    )


@pytest.fixture
def runs(seeker_account, admin_account):
    return [
        ScheduledRun.objects.create(user=seeker_account, status=ScheduledRun.Status.SUCCESS, platforms=["x"]),
        ScheduledRun.objects.create(user=admin_account, status=ScheduledRun.Status.FAILED, platforms=["naukri"]),
    ]


def _rows(response):
    data = response.data
    return data["results"] if isinstance(data, dict) and "results" in data else data


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def test_admin_gets_200_and_sees_every_users_runs(admin_account, runs):
    response = _client(admin_account).get(URL)
    assert response.status_code == 200
    assert {row["user_email"] for row in _rows(response)} == {"admin1@example.com", "seeker1@example.com"}


def test_job_seeker_gets_403(seeker_account, runs):
    assert _client(seeker_account).get(URL).status_code == 403


def test_anonymous_is_rejected(runs):
    assert _client().get(URL).status_code in (401, 403)


def test_filter_by_status(admin_account, runs):
    rows = _rows(_client(admin_account).get(URL, {"status": "failed"}))
    assert [row["status"] for row in rows] == ["failed"]


def test_filter_by_user(admin_account, seeker_account, runs):
    rows = _rows(_client(admin_account).get(URL, {"user": seeker_account.pk}))
    assert [row["user"] for row in rows] == [seeker_account.pk]


def test_invalid_status_is_400(admin_account):
    assert _client(admin_account).get(URL, {"status": "nonsense"}).status_code == 400


def test_admin_cannot_write(admin_account):
    assert _client(admin_account).post(URL, {}).status_code == 405
