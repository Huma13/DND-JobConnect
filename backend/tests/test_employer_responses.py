"""REQ-22/23 (TC-23, TC-24): users log employer replies and interviews, which drive response analytics."""
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .conftest import make_user
from .test_applications import make_item, start


@pytest.fixture
def applied(api):
    app_id = start(api, make_item(api.user)).json()["id"]
    assert api.post(f"/api/applications/{app_id}/mark-applied/").status_code == 200
    return app_id


@pytest.mark.django_db
def test_log_interview_and_list_it(api, applied):
    r = api.post(f"/api/applications/{applied}/responses/", {"response_type": "interview", "note": "Round 1 Mon"},
                 format="json")
    assert r.status_code == 201
    assert r.json()[0]["response_type"] == "interview"
    assert api.get(f"/api/applications/{applied}/responses/").json()[0]["note"] == "Round 1 Mon"


@pytest.mark.django_db
def test_logged_response_counts_in_response_rate(api, applied):
    api.post(f"/api/applications/{applied}/responses/", {"response_type": "reply"}, format="json")
    body = api.get("/api/applications/response-analytics/").json()
    assert body["response_count"] == 1
    assert body["response_rate"] == 100


@pytest.mark.django_db
def test_rejects_unknown_response_type(api, applied):
    r = api.post(f"/api/applications/{applied}/responses/", {"response_type": "offer"}, format="json")
    assert r.status_code == 400


@pytest.mark.django_db
def test_cannot_log_responses_on_someone_elses_application(api, applied):
    other = APIClient()
    other.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(make_user('x@pes.edu')).access_token}")
    r = other.post(f"/api/applications/{applied}/responses/", {"response_type": "reply"}, format="json")
    assert r.status_code == 404
