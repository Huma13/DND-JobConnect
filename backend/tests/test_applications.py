"""Issues #20-#27 (REQ-9 to REQ-13): apply kit, assisted/ATS/email apply, confirmation, limits, log, CAPTCHA."""
import pytest
import responses
from django.core import mail

from applications.models import (
    Application,
    ApplicationAttempt,
    ApplicationResponse,
    ApplicationStatusHistory,
    MailboxConfig,
    Notification,
)
from integrations.ats import GreenhouseAdapter, LeverAdapter, detect_ats, get_ats_adapter
from integrations.base import CaptchaDetected, SubmitError
from matching.models import FeedItem, JobPosting

GH_URL = "https://boards.greenhouse.io/acme/jobs/12345"
LEVER_URL = "https://jobs.lever.co/acme/0a1b2c3d-0a1b-0a1b-0a1b-0a1b2c3d4e5f"


def make_item(user, platform="naukri", url="https://www.naukri.com/job-listings-ml-1", ext="1",
              description="We use Python and PyTorch. Apply at jobs@acme.com"):
    posting = JobPosting.objects.create(platform=platform, external_id=ext, url=url, title="ML Engineer",
                                        company="Acme", description=description, dedup_key=ext, skills=["SQL"])
    return FeedItem.objects.create(user=user, posting=posting, relevance=80)


@pytest.fixture(autouse=True)
def _apply_settings(settings):
    settings.APPLICATION_EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.GREENHOUSE_API_KEY = "gh-key"
    settings.LEVER_API_KEY = "lever-key"


def start(api, item, **extra):
    return api.post("/api/applications/", {"feed_item": item.pk, **extra}, format="json")


# ---- #20 apply kit ----------------------------------------------------------------

@pytest.mark.django_db
def test_kit_is_built_from_profile_and_posting(api):
    item = make_item(api.user)
    r = api.post("/api/applications/kits/", {"feed_item": item.pk}, format="json")
    assert r.status_code == 201
    assert "Python" in r.data["resume_text"] and "PyTorch" in r.data["resume_text"]
    assert r.data["resume_text"].index("RELEVANT") < r.data["resume_text"].index("OTHER SKILLS")
    assert "Acme" in r.data["cover_letter"] and "ML Engineer" in r.data["cover_letter"]
    assert r.data["answers"]["Years of relevant experience"] == "2"


@pytest.mark.django_db
def test_kit_can_be_downloaded_copied_and_edited(api):
    item = make_item(api.user)
    kit = api.post("/api/applications/kits/", {"feed_item": item.pk}, format="json").data
    dl = api.get(f"/api/applications/kits/{kit['id']}/download/")
    assert dl["Content-Disposition"].startswith("attachment") and b"Dear Hiring Team" in dl.content
    assert b"SKILLS" not in api.get(f"/api/applications/kits/{kit['id']}/download/?part=cover_letter").content
    assert api.get(f"/api/applications/kits/{kit['id']}/").data["resume_text"] == kit["resume_text"]
    r = api.patch(f"/api/applications/kits/{kit['id']}/edit/", {"cover_letter": "Hello"}, format="json")
    assert r.data["cover_letter"] == "Hello"


@pytest.mark.django_db
def test_kit_for_unknown_or_foreign_item_is_rejected(api):
    from .conftest import make_user
    other = make_item(make_user("other@pes.edu"), ext="9")
    assert api.post("/api/applications/kits/", {"feed_item": other.pk}, format="json").status_code == 400


# ---- #21 assisted apply on LinkedIn / Naukri -----------------------------------------

@pytest.mark.django_db
def test_assisted_apply_returns_posting_and_kit_then_tracks_applied(api):
    item = make_item(api.user)
    r = start(api, item)
    assert r.status_code == 201
    assert r.data["posting_url"] == item.posting.url and r.data["kit"]["resume_text"]
    done = api.post(f"/api/applications/{r.data['id']}/mark-applied/")
    assert done.status_code == 200 and done.data["status"] == "applied"
    item.refresh_from_db()
    assert item.state == FeedItem.State.APPLIED
    assert api.post(f"/api/applications/{r.data['id']}/mark-applied/").status_code == 200  # idempotent
    assert ApplicationAttempt.objects.filter(application_id=r.data["id"]).count() == 1


@pytest.mark.django_db
def test_assisted_apply_is_only_for_linkedin_and_naukri(api):
    item = make_item(api.user, platform="x", url="https://x.com/hr/status/5")
    assert start(api, item).status_code == 400


@pytest.mark.django_db
def test_manual_application_cannot_be_submitted_by_the_app(api):
    app_id = start(api, make_item(api.user)).data["id"]
    assert api.post(f"/api/applications/{app_id}/submit/", {"confirmed": True}, format="json").status_code == 400


# ---- #22 ATS auto-apply ---------------------------------------------------------------

def test_detect_ats():
    assert detect_ats(GH_URL) == "greenhouse" and detect_ats(LEVER_URL) == "lever"
    assert detect_ats("https://example.com/careers/1") is None


@pytest.mark.django_db
def test_ats_requires_a_greenhouse_or_lever_posting(api):
    assert start(api, make_item(api.user), method="ats").status_code == 400


@pytest.mark.django_db
@responses.activate
def test_greenhouse_submit_after_confirmation_saves_result(api):
    responses.post("https://boards-api.greenhouse.io/v1/boards/acme/jobs/12345", json={"success": True})
    item = make_item(api.user, platform="linkedin", url=GH_URL)
    app = start(api, item, method="ats").data
    assert app["platform"] == "greenhouse"
    r = api.post(f"/api/applications/{app['id']}/submit/", {"confirmed": True}, format="json")
    assert r.status_code == 200 and r.data["status"] == "submitted"
    assert r.data["result"] == {"ats": "greenhouse", "http_status": 200}
    body = responses.calls[0].request.body
    assert "cover_letter_text" in body and "seeker%40pes.edu" in body
    item.refresh_from_db()
    assert item.state == FeedItem.State.APPLIED


@pytest.mark.django_db
@responses.activate
def test_lever_submit(api):
    responses.post("https://api.lever.co/v0/postings/acme/0a1b2c3d-0a1b-0a1b-0a1b-0a1b2c3d4e5f", json={"ok": True})
    app = start(api, make_item(api.user, platform="linkedin", url=LEVER_URL), method="ats").data
    r = api.post(f"/api/applications/{app['id']}/submit/", {"confirmed": True}, format="json")
    assert r.data["status"] == "submitted" and r.data["platform"] == "lever"
    assert "key=lever-key" in responses.calls[0].request.url


@pytest.mark.django_db
@responses.activate
def test_ats_rejection_is_recorded_as_failure(api):
    responses.post("https://boards-api.greenhouse.io/v1/boards/acme/jobs/12345", status=422, body="invalid")
    app = start(api, make_item(api.user, url=GH_URL), method="ats").data
    r = api.post(f"/api/applications/{app['id']}/submit/", {"confirmed": True}, format="json")
    assert r.data["status"] == "failed" and "422" in r.data["result"]["error"]
    assert ApplicationAttempt.objects.get().status == "failure"


def test_adapter_error_paths(settings):
    with pytest.raises(SubmitError):
        get_ats_adapter("workday")
    with pytest.raises(SubmitError):
        GreenhouseAdapter().submit("https://example.com/x", {"name": "A", "email": "a@b.co"}, {})
    with pytest.raises(SubmitError):
        LeverAdapter().submit("https://example.com/x", {"name": "A", "email": "a@b.co"}, {})
    settings.GREENHOUSE_API_KEY = settings.LEVER_API_KEY = ""
    kit = {"cover_letter": "c", "resume_text": "r"}
    with pytest.raises(SubmitError, match="GREENHOUSE_API_KEY"):
        GreenhouseAdapter().submit(GH_URL, {"name": "A B", "email": "a@b.co"}, kit)
    with pytest.raises(SubmitError, match="LEVER_API_KEY"):
        LeverAdapter().submit(LEVER_URL, {"name": "A B", "email": "a@b.co"}, kit)


@responses.activate
def test_adapters_wrap_network_errors(settings):
    import requests
    kit = {"cover_letter": "c", "resume_text": "r"}
    responses.post("https://boards-api.greenhouse.io/v1/boards/acme/jobs/12345", body=requests.ConnectionError())
    responses.post("https://api.lever.co/v0/postings/acme/0a1b2c3d-0a1b-0a1b-0a1b-0a1b2c3d4e5f",
                   body=requests.ConnectionError())
    settings.GREENHOUSE_API_KEY = settings.LEVER_API_KEY = "k"
    with pytest.raises(SubmitError, match="Greenhouse"):
        GreenhouseAdapter().submit(GH_URL, {"name": "A", "email": "a@b.co"}, kit)
    with pytest.raises(SubmitError, match="Lever"):
        LeverAdapter().submit(LEVER_URL, {"name": "A", "email": "a@b.co"}, kit)


# ---- #23 email apply ------------------------------------------------------------------

MAILBOX = {"host": "smtp.example.com", "port": 587, "username": "me", "password": "s3cret!",
           "from_email": "seeker@pes.edu", "use_tls": True}


@pytest.mark.django_db
def test_mailbox_password_is_encrypted_and_never_returned(api):
    assert api.get("/api/applications/mailbox/").status_code == 404
    r = api.put("/api/applications/mailbox/", MAILBOX, format="json")
    assert r.status_code == 200 and "password" not in r.data
    assert "password" not in api.get("/api/applications/mailbox/").data
    stored = MailboxConfig.objects.get().password_encrypted
    assert "s3cret" not in stored


@pytest.mark.django_db
def test_email_apply_sends_from_own_mailbox_with_resume_after_confirmation(api):
    api.put("/api/applications/mailbox/", MAILBOX, format="json")
    app = start(api, make_item(api.user), method="email").data
    assert app["to_email"] == "jobs@acme.com"  # found in the posting
    r = api.post(f"/api/applications/{app['id']}/submit/", {"confirmed": True}, format="json")
    assert r.status_code == 200 and r.data["status"] == "submitted"
    msg = mail.outbox[0]
    assert msg.to == ["jobs@acme.com"] and msg.from_email == "seeker@pes.edu"
    assert msg.attachments[0][0] == "resume.txt" and "Python" in msg.attachments[0][1]
    assert "Dear Hiring Team" in msg.body


@pytest.mark.django_db
def test_email_apply_needs_a_recipient_and_a_mailbox(api):
    item = make_item(api.user, description="no contact here")
    assert start(api, item, method="email").status_code == 400
    assert start(api, item, method="email", to_email="not-an-email").status_code == 400
    app = start(api, item, method="email", to_email="hr@acme.com").data
    r = api.post(f"/api/applications/{app['id']}/submit/", {"confirmed": True}, format="json")
    assert r.data["status"] == "failed" and "mailbox" in r.data["result"]["error"]


@pytest.mark.django_db
def test_email_delivery_error_is_recorded(api, monkeypatch):
    api.put("/api/applications/mailbox/", MAILBOX, format="json")
    app = start(api, make_item(api.user), method="email").data

    def boom(self, *a, **k):
        raise OSError("smtp down")
    monkeypatch.setattr("django.core.mail.EmailMessage.send", boom)
    r = api.post(f"/api/applications/{app['id']}/submit/", {"confirmed": True}, format="json")
    assert r.data["status"] == "failed" and "OSError" in r.data["result"]["error"]


@pytest.mark.django_db
def test_unknown_method_rejected(api):
    assert start(api, make_item(api.user), method="carrier-pigeon").status_code == 400


# ---- #24 confirmation (REQ-10) --------------------------------------------------------

@pytest.mark.django_db
@responses.activate
def test_submit_needs_confirmation_unless_full_auto_for_that_platform(api):
    responses.post("https://boards-api.greenhouse.io/v1/boards/acme/jobs/12345", json={})
    app = start(api, make_item(api.user, url=GH_URL), method="ats").data
    review = api.get(f"/api/applications/{app['id']}/review/")
    assert review.data["requires_confirmation"] is True and review.data["cover_letter"]
    r = api.post(f"/api/applications/{app['id']}/submit/", {}, format="json")
    assert r.status_code == 428 and len(responses.calls) == 0
    assert api.post(f"/api/applications/{app['id']}/submit/", {"confirmed": False}, format="json").status_code == 428

    api.put("/api/applications/limits/", {"platform": "greenhouse", "full_auto": True}, format="json")
    assert api.get(f"/api/applications/{app['id']}/review/").data["requires_confirmation"] is False
    assert api.post(f"/api/applications/{app['id']}/submit/", {}, format="json").data["status"] == "submitted"


@pytest.mark.django_db
@responses.activate
def test_full_auto_on_one_platform_does_not_skip_review_on_another(api):
    api.put("/api/applications/limits/", {"platform": "lever", "full_auto": True}, format="json")
    app = start(api, make_item(api.user, url=GH_URL), method="ats").data
    assert api.post(f"/api/applications/{app['id']}/submit/", {}, format="json").status_code == 428


@pytest.mark.django_db
@responses.activate
def test_a_submitted_application_cannot_be_submitted_twice(api):
    responses.post("https://boards-api.greenhouse.io/v1/boards/acme/jobs/12345", json={})
    app = start(api, make_item(api.user, url=GH_URL), method="ats").data
    api.post(f"/api/applications/{app['id']}/submit/", {"confirmed": True}, format="json")
    assert api.post(f"/api/applications/{app['id']}/submit/", {"confirmed": True}, format="json").status_code == 409
    assert len(responses.calls) == 1


# ---- #25 daily limit (REQ-11) ---------------------------------------------------------

@pytest.mark.django_db
def test_default_limit_is_20_and_can_be_changed(api):
    rows = {r["platform"]: r for r in api.get("/api/applications/limits/").data}
    assert rows["linkedin"]["daily_limit"] == 20 and rows["linkedin"]["used_today"] == 0
    r = api.put("/api/applications/limits/", {"platform": "linkedin", "daily_limit": 2}, format="json")
    assert {x["platform"]: x for x in r.data}["linkedin"]["daily_limit"] == 2
    assert api.put("/api/applications/limits/", {"platform": "fax", "daily_limit": 2}, format="json").status_code == 400
    assert api.put("/api/applications/limits/", {"platform": "x", "daily_limit": -1}, format="json").status_code == 400


@pytest.mark.django_db
def test_over_the_limit_is_blocked(api):
    api.put("/api/applications/limits/", {"platform": "naukri", "daily_limit": 2}, format="json")
    for i in range(2):
        app = start(api, make_item(api.user, ext=f"n{i}")).data
        assert api.post(f"/api/applications/{app['id']}/mark-applied/").status_code == 200
    assert start(api, make_item(api.user, ext="n3")).status_code == 429


@pytest.mark.django_db
@responses.activate
def test_limit_blocks_auto_submit_but_not_other_platforms(api):
    responses.post("https://boards-api.greenhouse.io/v1/boards/acme/jobs/12345", json={})
    api.put("/api/applications/limits/", {"platform": "greenhouse", "daily_limit": 1}, format="json")
    first = start(api, make_item(api.user, url=GH_URL, ext="a"), method="ats").data
    second = start(api, make_item(api.user, url=GH_URL, ext="b"), method="ats").data
    assert api.post(f"/api/applications/{first['id']}/submit/", {"confirmed": True}, format="json").status_code == 200
    blocked = api.post(f"/api/applications/{second['id']}/submit/", {"confirmed": True}, format="json")
    assert blocked.status_code == 429 and "limit" in blocked.data["detail"]
    assert start(api, make_item(api.user, ext="c")).status_code == 201  # naukri unaffected


@pytest.mark.django_db
def test_limit_counts_only_today(api):
    from datetime import timedelta

    from django.utils import timezone
    api.put("/api/applications/limits/", {"platform": "naukri", "daily_limit": 1}, format="json")
    app = Application.objects.get(pk=start(api, make_item(api.user)).data["id"])
    old = ApplicationAttempt.objects.create(user=api.user, application=app, platform="naukri", status="success")
    ApplicationAttempt.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=1))
    assert start(api, make_item(api.user, ext="z")).status_code == 201


# ---- #26 attempt log (REQ-12) ---------------------------------------------------------

@pytest.mark.django_db
@responses.activate
def test_every_attempt_is_saved_with_timestamp_and_status(api):
    responses.post("https://boards-api.greenhouse.io/v1/boards/acme/jobs/12345", status=500, body="oops")
    responses.post("https://boards-api.greenhouse.io/v1/boards/acme/jobs/12345", status=200, json={})
    responses.post("https://boards-api.greenhouse.io/v1/boards/acme/jobs/12345", status=403, body="Complete the CAPTCHA")
    for ext in "abc":
        app = start(api, make_item(api.user, url=GH_URL, ext=ext), method="ats").data
        api.post(f"/api/applications/{app['id']}/submit/", {"confirmed": True}, format="json")
    r = api.get("/api/applications/attempts/")
    assert [a["status"] for a in reversed(r.data["results"])] == ["failure", "success", "captcha"]
    assert all(a["created_at"] for a in r.data["results"])
    assert len(api.get("/api/applications/attempts/?status=captcha").data["results"]) == 1
    detail = api.get(f"/api/applications/{app['id']}/")
    assert detail.data["attempts"][0]["status"] == "captcha"
    assert len(api.get("/api/applications/?status=manual_review_required").data["results"]) == 1


@pytest.mark.django_db
def test_attempts_are_private_to_their_user(api):
    from .conftest import make_user
    other = make_user("other@pes.edu")
    app = Application.objects.get(pk=start(api, make_item(api.user)).data["id"])
    ApplicationAttempt.objects.create(user=other, application=app, platform="naukri", status="success")
    assert api.get("/api/applications/attempts/").data["count"] == 0


# ---- #27 CAPTCHA (REQ-13) -------------------------------------------------------------

@pytest.mark.django_db
@responses.activate
def test_captcha_pauses_sets_manual_review_and_notifies(api):
    responses.post("https://boards-api.greenhouse.io/v1/boards/acme/jobs/12345", status=403,
                   body="Please verify you are human")
    app = start(api, make_item(api.user, url=GH_URL), method="ats").data
    r = api.post(f"/api/applications/{app['id']}/submit/", {"confirmed": True}, format="json")
    assert r.data["status"] == "manual_review_required"
    assert ApplicationAttempt.objects.get().status == "captcha"
    note = api.get("/api/applications/notifications/").data["results"][0]
    assert note["kind"] == "captcha" and "Manual review" in note["message"] and note["application"] == app["id"]
    assert api.post(f"/api/applications/notifications/{note['id']}/read/").status_code == 204
    assert Notification.objects.get().read is True
    item = FeedItem.objects.get(user=api.user)
    assert item.state != FeedItem.State.APPLIED  # nothing was submitted


@pytest.mark.django_db
def test_adapter_raising_captcha_is_handled(api, monkeypatch):
    class Fake:
        def submit(self, *a):
            raise CaptchaDetected("hCaptcha")
    monkeypatch.setattr("applications.services.get_ats_adapter", lambda name: Fake())
    app = start(api, make_item(api.user, url=GH_URL), method="ats").data
    r = api.post(f"/api/applications/{app['id']}/submit/", {"confirmed": True}, format="json")
    assert r.data["status"] == "manual_review_required"


@pytest.mark.django_db
def test_after_manual_review_the_user_can_try_again(api, monkeypatch):
    calls = []

    class Fake:
        def submit(self, *a):
            calls.append(1)
            if len(calls) == 1:
                raise CaptchaDetected("captcha")
            return {"ok": True}
    monkeypatch.setattr("applications.services.get_ats_adapter", lambda name: Fake())
    app = start(api, make_item(api.user, url=GH_URL), method="ats").data
    url = f"/api/applications/{app['id']}/submit/"
    assert api.post(url, {"confirmed": True}, format="json").data["status"] == "manual_review_required"
    assert api.post(url, {"confirmed": True}, format="json").data["status"] == "submitted"


# ---- Pause All (SRS 6.2) --------------------------------------------------------------

@pytest.mark.django_db
def test_pause_all_blocks_submission(api):
    app = start(api, make_item(api.user, url=GH_URL), method="ats").data
    api.post("/api/auth/pause/", {"paused": True}, format="json")
    r = api.post(f"/api/applications/{app['id']}/submit/", {"confirmed": True}, format="json")
    assert r.status_code == 409


# ---- #36 Manual application status change -----------------------------------

@pytest.mark.django_db
def test_manual_status_change_is_saved_with_history(api):
    item = make_item(api.user)
    app = start(api, item).data

    response = api.patch(
        f"/api/applications/{app['id']}/change-status/",
        {"status": "applied"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["status"] == "applied"

    history = ApplicationStatusHistory.objects.get(application_id=app["id"])
    assert history.old_status == "draft"
    assert history.new_status == "applied"
    assert history.user == api.user


@pytest.mark.django_db
def test_manual_status_change_same_status_does_not_create_history(api):
    item = make_item(api.user)
    app = start(api, item).data

    response = api.patch(
        f"/api/applications/{app['id']}/change-status/",
        {"status": "draft"},
        format="json",
    )

    assert response.status_code == 200
    assert ApplicationStatusHistory.objects.filter(application_id=app["id"]).count() == 0


@pytest.mark.django_db
def test_manual_status_change_rejects_invalid_status(api):
    item = make_item(api.user)
    app = start(api, item).data

    response = api.patch(
        f"/api/applications/{app['id']}/change-status/",
        {"status": "invalid"},
        format="json",
    )

    assert response.status_code == 400
    assert ApplicationStatusHistory.objects.filter(application_id=app["id"]).count() == 0


@pytest.mark.django_db
def test_user_cannot_change_another_users_application(api):
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    from .conftest import make_user

    other_user = make_user("other@example.com")
    item = make_item(other_user, ext="foreign-36")

    # Create an application belonging to the other user.
    other_api = APIClient()
    other_api.credentials(
        HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(other_user).access_token}"
    )
    app = start(other_api, item).data

    # Try changing it using the original user's API client.
    response = api.patch(
        f"/api/applications/{app['id']}/change-status/",
        {"status": "applied"},
        format="json",
    )

    assert response.status_code == 404
    assert ApplicationStatusHistory.objects.filter(
        application_id=app["id"]
    ).count() == 0


# ---- #38 Export application history as CSV -------------------------------

@pytest.mark.django_db
def test_application_history_can_be_exported_as_csv(api):
    item = make_item(api.user)
    start(api, item)

    response = api.get("/api/applications/export/")

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"
    assert "attachment; filename=\"application_history.csv\"" in response[
        "Content-Disposition"
    ]

    content = response.content.decode("utf-8")
    assert "Application ID" in content
    assert "Job Title" in content
    assert "Company" in content


@pytest.mark.django_db
def test_application_csv_contains_application_details(api):
    item = make_item(api.user)
    app = start(api, item).data

    response = api.get("/api/applications/export/")
    content = response.content.decode("utf-8")

    assert str(app["id"]) in content
    assert item.posting.title in content
    assert item.posting.company in content





@pytest.mark.django_db
def test_application_csv_only_contains_current_users_applications(api):
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    from .conftest import make_user

    # Create an application for the logged-in user.
    item = make_item(api.user)
    start(api, item)

    # Create another user's application.
    other_user = make_user("other-csv@example.com")
    other_item = make_item(other_user, ext="foreign-csv")
    other_item.posting.title = "Foreign User Exclusive Job"
    other_item.posting.save(update_fields=["title"])

    other_api = APIClient()
    other_api.credentials(
        HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(other_user).access_token}"
    )
    start(other_api, other_item)

    # Export using the original user's client.
    response = api.get("/api/applications/export/")
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert item.posting.title in content
    assert other_item.posting.title not in content

# ---- #39 keyword response analytics -----------------------------------------------

@pytest.mark.django_db
def test_keyword_analytics_counts_applications_and_responses(api):
    item1 = make_item(api.user, ext="keyword-1")
    item1.posting.skills = ["Python", "SQL"]
    item1.posting.save()

    item2 = make_item(api.user, ext="keyword-2")
    item2.posting.skills = ["Python", "Docker"]
    item2.posting.save()

    app1_id = start(api, item1).data["id"]
    app2_id = start(api, item2).data["id"]

    api.post(f"/api/applications/{app1_id}/mark-applied/")
    api.post(f"/api/applications/{app2_id}/mark-applied/")

    app1 = Application.objects.get(pk=app1_id)

    ApplicationResponse.objects.create(
        application=app1,
        user=api.user,
        response_type=ApplicationResponse.Type.REPLY,
        note="Employer replied",
    )

    response = api.get("/api/applications/keyword-analytics/")

    assert response.status_code == 200

    results = {item["keyword"]: item for item in response.data["keywords"]}

    assert results["Python"]["application_count"] == 2
    assert results["Python"]["response_count"] == 1
    assert results["Python"]["response_rate"] == 50.0

    assert results["SQL"]["application_count"] == 1
    assert results["SQL"]["response_count"] == 1

    assert results["Docker"]["application_count"] == 1
    assert results["Docker"]["response_count"] == 0


@pytest.mark.django_db
def test_keyword_analytics_does_not_double_count_multiple_responses(api):
    item = make_item(api.user, ext="keyword-multiple")
    item.posting.skills = ["Python"]
    item.posting.save()

    app_id = start(api, item).data["id"]
    api.post(f"/api/applications/{app_id}/mark-applied/")

    application = Application.objects.get(pk=app_id)

    for response_type in (
        ApplicationResponse.Type.REPLY,
        ApplicationResponse.Type.INTERVIEW,
    ):
        ApplicationResponse.objects.create(
            application=application,
            user=api.user,
            response_type=response_type,
        )

    response = api.get("/api/applications/keyword-analytics/")
    python_result = next(
        item for item in response.data["keywords"]
        if item["keyword"] == "Python"
    )

    assert python_result["application_count"] == 1
    assert python_result["response_count"] == 1
    assert python_result["response_rate"] == 100.0


@pytest.mark.django_db
def test_keyword_analytics_does_not_include_other_users_applications(api):
    from .conftest import make_user

    other_user = make_user("other-keyword@pes.edu", skills=["Python"])

    item = make_item(other_user, ext="other-keyword")
    item.posting.skills = ["Python"]
    item.posting.save()

    response = api.get("/api/applications/keyword-analytics/")

    python_result = next(
        item for item in response.data["keywords"]
        if item["keyword"] == "Python"
    )

    assert python_result["application_count"] == 0
    assert python_result["response_count"] == 0


# ---- #35 application statistics by platform and status ----------------------------

@pytest.mark.django_db
def test_application_statistics_counts_by_platform_and_status(api):
    naukri_item = make_item(api.user, platform="naukri", ext="stats-naukri")
    linkedin_item = make_item(
        api.user,
        platform="linkedin",
        url="https://www.linkedin.com/jobs/view/12345",
        ext="stats-linkedin",
    )

    start(api, naukri_item)
    linkedin_app = start(api, linkedin_item).data

    # Change one application from draft to applied.
    api.post(f"/api/applications/{linkedin_app['id']}/mark-applied/")

    response = api.get(
        "/api/applications/statistics/",
        {"start_date": "2026-01-01", "end_date": "2026-12-31"},
    )

    assert response.status_code == 200
    assert response.data["total_applications"] == 2

    assert {
        item["platform"]: item["count"]
        for item in response.data["by_platform"]
    } == {
        "naukri": 1,
        "linkedin": 1,
    }

    assert {
        item["status"]: item["count"]
        for item in response.data["by_status"]
    } == {
        "draft": 1,
        "applied": 1,
    }


@pytest.mark.django_db
def test_application_statistics_filters_by_date_range(api):
    from datetime import timedelta

    from django.utils import timezone

    item1 = make_item(api.user, ext="stats-date-inside")
    item2 = make_item(api.user, ext="stats-date-outside")

    app1 = start(api, item1).data
    app2 = start(api, item2).data

    today = timezone.now()
    Application.objects.filter(pk=app1["id"]).update(
        created_at=today - timedelta(days=2)
    )
    Application.objects.filter(pk=app2["id"]).update(
        created_at=today - timedelta(days=10)
    )

    selected_date = (today - timedelta(days=3)).date()

    response = api.get(
        "/api/applications/statistics/",
        {
            "start_date": selected_date.isoformat(),
            "end_date": today.date().isoformat(),
        },
    )

    assert response.status_code == 200
    assert response.data["total_applications"] == 1


@pytest.mark.django_db
def test_application_statistics_excludes_other_users(api):
    from .conftest import make_user

    other_user = make_user("other-stats@example.com")
    other_item = make_item(other_user, ext="stats-other-user")

    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    other_api = APIClient()
    other_api.credentials(
        HTTP_AUTHORIZATION=(
            f"Bearer {RefreshToken.for_user(other_user).access_token}"
        )
    )
    start(other_api, other_item)

    response = api.get(
        "/api/applications/statistics/",
        {"start_date": "2026-01-01", "end_date": "2026-12-31"},
    )

    assert response.status_code == 200
    assert response.data["total_applications"] == 0
    assert response.data["by_platform"] == []
    assert response.data["by_status"] == []


@pytest.mark.django_db
def test_application_statistics_requires_both_dates(api):
    response = api.get(
        "/api/applications/statistics/",
        {"start_date": "2026-01-01"},
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_application_statistics_rejects_invalid_date_range(api):
    response = api.get(
        "/api/applications/statistics/",
        {"start_date": "2026-12-31", "end_date": "2026-01-01"},
    )

    assert response.status_code == 400
