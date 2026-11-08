"""Issue #4: automation does not start until the legal disclaimer is accepted."""

import pytest
from rest_framework.test import APIClient

from accounts.disclaimer import DISCLAIMER_VERSION
from accounts.gates import DISCLAIMER_REQUIRED
from accounts.models import User
from resume_parser.models import Profile
from scheduler.models import ScheduledRun
from scheduler.tasks import execute_run


@pytest.fixture(autouse=True)
def disclaimer_on(settings):
    settings.REQUIRE_DISCLAIMER = True


@pytest.fixture
def seeker(db):
    return User.objects.create_user(username="s", email="s@example.com", password="Pass12345!")


@pytest.fixture
def client(seeker):
    api = APIClient()
    api.force_authenticate(seeker)
    return api


@pytest.mark.parametrize(
    "path",
    [
        "/api/jobs/feed/search/",  # manual search
        "/api/applications/1/submit/",  # submit an application
        "/api/outreach/messages/1/send/",  # send an outreach message
    ],
)
@pytest.mark.django_db
def test_automation_endpoints_refuse_until_the_disclaimer_is_accepted(client, path):
    response = client.post(path, {"confirmed": True}, format="json")
    assert response.status_code == 403
    assert response.data["code"] == "disclaimer_required"
    assert response.data["detail"] == DISCLAIMER_REQUIRED


@pytest.mark.django_db
def test_a_scheduled_run_is_skipped_until_the_disclaimer_is_accepted(seeker):
    run = execute_run(ScheduledRun.objects.create(user=seeker))
    assert run.status == ScheduledRun.Status.SKIPPED
    assert run.errors == [{"platform": "*", "error": DISCLAIMER_REQUIRED}]
    assert run.finished_at is not None


@pytest.mark.django_db
def test_manual_search_is_no_longer_blocked_after_accepting(client, seeker, monkeypatch):
    seeker.disclaimer_accepted_at = seeker.date_joined
    seeker.disclaimer_version = DISCLAIMER_VERSION
    seeker.save()
    Profile.objects.create(
    user=seeker,
    preferred_roles=["Software Developer"],
    )
    monkeypatch.setattr("matching.views.search_task.delay", lambda *args, **kwargs: None)
    response = client.post("/api/jobs/feed/search/")
    assert response.status_code == 202
