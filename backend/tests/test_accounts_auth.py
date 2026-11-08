"""Issue #1: register and log in (SRS 6.3, 6.5)."""

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User

REGISTER = "/api/auth/register/"
LOGIN = "/api/auth/login/"
REFRESH = "/api/auth/refresh/"
PAUSE = "/api/auth/pause/"
PASSWORD = "Str0ng-Pass-98"


@pytest.fixture
def api():
    return APIClient()


def _register(api, email="seeker@example.com", password=PASSWORD, **extra):
    return api.post(REGISTER, {"email": email, "password": password, **extra}, format="json")


def _login(api, email="seeker@example.com", password=PASSWORD):
    return api.post(LOGIN, {"email": email, "password": password}, format="json")


# ------------------------------------------------------------------ registration


@pytest.mark.django_db
def test_register_creates_a_job_seeker_and_never_returns_the_password(api):
    response = _register(api)
    assert response.status_code == 201
    assert set(response.data) == {"id", "email"}
    user = User.objects.get(email="seeker@example.com")
    assert user.role == User.Role.JOB_SEEKER
    assert not user.is_staff
    assert not user.is_superuser


@pytest.mark.django_db
def test_register_ignores_role_and_privilege_fields(api):
    response = _register(api, role="admin", is_staff=True, is_superuser=True, is_active=False)
    assert response.status_code == 201
    user = User.objects.get(email="seeker@example.com")
    assert user.role == User.Role.JOB_SEEKER
    assert not user.is_staff
    assert not user.is_superuser
    assert user.is_active


@pytest.mark.django_db
def test_passwords_are_stored_hashed_with_argon2(api):
    _register(api)
    stored = User.objects.get(email="seeker@example.com").password
    assert stored.startswith("argon2$")
    assert PASSWORD not in stored


@pytest.mark.django_db
@pytest.mark.parametrize("weak", ["short1", "password", "12345678", "aaaaaaaa"])
def test_weak_passwords_are_rejected(api, weak):
    response = _register(api, password=weak)
    assert response.status_code == 400
    assert "password" in response.data
    assert not User.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("payload", [{}, {"email": "a@example.com"}, {"password": PASSWORD}])
def test_email_and_password_are_required(api, payload):
    assert api.post(REGISTER, payload, format="json").status_code == 400


@pytest.mark.django_db
def test_invalid_email_is_rejected(api):
    response = _register(api, email="not-an-email")
    assert response.status_code == 400
    assert "email" in response.data


@pytest.mark.django_db
@pytest.mark.parametrize("second", ["seeker@example.com", "SEEKER@Example.com"])
def test_duplicate_emails_are_rejected_whatever_the_letter_case(api, second):
    assert _register(api).status_code == 201
    response = _register(api, email=second)
    assert response.status_code == 400
    assert "email" in response.data
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_an_email_too_long_for_the_username_column_is_a_400_not_a_crash(api):
    long_email = "user@" + ("d" * 50 + ".") * 3 + "com"
    assert len(long_email) > 150
    response = _register(api, email=long_email)
    assert response.status_code == 400
    assert "email" in response.data


# --------------------------------------------------------------------------- login


@pytest.mark.django_db
def test_login_returns_access_and_refresh_tokens(api):
    _register(api)
    response = _login(api)
    assert response.status_code == 200
    assert response.data["access"]
    assert response.data["refresh"]


@pytest.mark.django_db
def test_access_token_lasts_30_minutes(api):
    _register(api)
    token = AccessToken(_login(api).data["access"])
    assert token["exp"] - token["iat"] == 30 * 60


@pytest.mark.django_db
def test_wrong_password_and_unknown_user_get_401(api):
    _register(api)
    assert _login(api, password="Wrong-Pass-123").status_code == 401
    assert _login(api, email="nobody@example.com").status_code == 401


@pytest.mark.django_db
def test_login_is_open_but_other_endpoints_need_a_token(api):
    _register(api)
    assert api.post(PAUSE, {"paused": True}, format="json").status_code == 401
    access = _login(api).data["access"]
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    response = api.post(PAUSE, {"paused": True}, format="json")
    assert response.status_code == 200
    assert response.data == {"automation_paused": True}


@pytest.mark.django_db
def test_refresh_token_gives_a_working_new_access_token(api):
    _register(api)
    refresh = _login(api).data["refresh"]
    response = api.post(REFRESH, {"refresh": refresh}, format="json")
    assert response.status_code == 200
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    assert api.post(PAUSE, {"paused": False}, format="json").status_code == 200


@pytest.mark.django_db
def test_a_refresh_token_is_not_accepted_as_an_access_token(api):
    _register(api)
    refresh = _login(api).data["refresh"]
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh}")
    assert api.post(PAUSE, {"paused": True}, format="json").status_code == 401
