
import base64
import json

import pytest
from rest_framework.test import APIClient

from applications.credential_crypto import decrypt_credential
from applications.models import PlatformCredential


@pytest.fixture(autouse=True)
def platform_encryption_key(settings):
    settings.PLATFORM_CREDENTIAL_ENCRYPTION_KEY = base64.urlsafe_b64encode(
        b"0123456789abcdef0123456789abcdef"
    ).decode("ascii")


@pytest.mark.django_db
def test_platform_credentials_are_encrypted_and_write_only(api):
    credentials = {
        "access_token": "linkedin-secret-token",
        "refresh_token": "linkedin-refresh-secret",
    }

    response = api.post(
        "/api/applications/platform-credentials/",
        {"platform": "linkedin", "credentials": credentials},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["platform"] == "linkedin"
    assert "credentials" not in response.data
    assert "access_token" not in response.data

    stored = PlatformCredential.objects.get(
        user=api.user,
        platform="linkedin",
    )

    assert "linkedin-secret-token" not in stored.credentials_encrypted
    assert "linkedin-refresh-secret" not in stored.credentials_encrypted

    decrypted = decrypt_credential(stored.credentials_encrypted)
    assert json.loads(decrypted) == credentials

    assert api.get(
        "/api/applications/platform-credentials/"
    ).status_code == 405


@pytest.mark.django_db
def test_platform_credentials_update_existing_record(api):
    url = "/api/applications/platform-credentials/"

    first = api.post(
        url,
        {
            "platform": "linkedin",
            "credentials": {"access_token": "first-secret"},
        },
        format="json",
    )
    assert first.status_code == 201

    second = api.post(
        url,
        {
            "platform": "linkedin",
            "credentials": {"access_token": "second-secret"},
        },
        format="json",
    )

    assert second.status_code == 200
    assert PlatformCredential.objects.filter(
        user=api.user,
        platform="linkedin",
    ).count() == 1

    stored = PlatformCredential.objects.get(
        user=api.user,
        platform="linkedin",
    )
    assert json.loads(
        decrypt_credential(stored.credentials_encrypted)
    ) == {"access_token": "second-secret"}


@pytest.mark.django_db
def test_platform_credentials_reject_invalid_input(api):
    url = "/api/applications/platform-credentials/"

    empty_credentials = api.post(
        url,
        {"platform": "linkedin", "credentials": {}},
        format="json",
    )
    assert empty_credentials.status_code == 400

    invalid_platform = api.post(
        url,
        {"platform": "invalid", "credentials": {"token": "secret"}},
        format="json",
    )
    assert invalid_platform.status_code == 400


@pytest.mark.django_db
def test_platform_credentials_require_authentication():
    client = APIClient()

    response = client.post(
        "/api/applications/platform-credentials/",
        {
            "platform": "linkedin",
            "credentials": {"access_token": "secret"},
        },
        format="json",
    )

    assert response.status_code in (401, 403)
