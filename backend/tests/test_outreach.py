"""Issues #28-#31 (REQ-14 to REQ-17): recruiter suggestions, editable drafts, daily limits, bulk-message block."""
import pytest

from integrations.base import SubmitError, SubmitRateLimited
from matching.models import FeedItem, JobPosting
from outreach.models import OutreachMessage, Recruiter

DESC = ("We use Python and PyTorch. Talk to Priya https://www.linkedin.com/in/priya-sharma/ "
        "or ping @acme_hr. Email me at hr@acme.com")


def make_item(user, ext="1", platform="linkedin", url="https://www.linkedin.com/jobs/view/1", description=DESC):
    posting = JobPosting.objects.create(platform=platform, external_id=ext, url=url, title="ML Engineer",
                                        company="Acme", description=description, dedup_key=ext)
    return FeedItem.objects.create(user=user, posting=posting, relevance=70)


class FakeX:
    def __init__(self, error=None):
        self.sent, self.error = [], error

    def send(self, handle, text):
        if self.error:
            raise self.error
        self.sent.append((handle, text))
        return "evt-1"


@pytest.fixture
def fake_x(monkeypatch):
    fake = FakeX()
    monkeypatch.setattr("outreach.services.get_x_messenger", lambda: fake)
    return fake


def recruiters(api, item):
    return api.get(f"/api/outreach/recruiters/?feed_item={item.pk}").data


def draft(api, recruiter_id, platform=None):
    body = {"recruiter": recruiter_id, **({"platform": platform} if platform else {})}
    return api.post("/api/outreach/messages/", body, format="json")


# ---- #28 suggestions (REQ-14) ---------------------------------------------------------

@pytest.mark.django_db
def test_recruiters_listed_with_reason_and_best_channel(api):
    item = make_item(api.user)
    data = recruiters(api, item)
    by_name = {r["name"]: r for r in data}
    assert by_name["Priya Sharma"]["best_channel"] == "linkedin_note"
    assert "Acme" in by_name["Priya Sharma"]["reason"]
    assert by_name["@acme_hr"]["best_channel"] == "x_message" and by_name["@acme_hr"]["reason"]
    assert len(recruiters(api, item)) == len(data) == Recruiter.objects.count()  # no duplicates on refresh


@pytest.mark.django_db
def test_x_posting_author_is_the_top_suggestion(api):
    item = make_item(api.user, platform="x", url="https://x.com/talent_lead/status/998", description="Hiring!")
    data = recruiters(api, item)
    assert data[0]["x_handle"] == "talent_lead" and "Posted this role" in data[0]["reason"]


@pytest.mark.django_db
def test_posting_with_no_contacts_gives_an_empty_list_and_manual_add_works(api):
    item = make_item(api.user, description="nothing useful")
    assert recruiters(api, item) == []
    r = api.post("/api/outreach/recruiters/", {"feed_item": item.pk, "name": "Sam", "linkedin_url":
                 "https://www.linkedin.com/in/sam"}, format="json")
    assert r.status_code == 201 and r.data["reason"] == "Added by you."
    assert len(recruiters(api, item)) == 1
    bad = api.post("/api/outreach/recruiters/", {"feed_item": item.pk, "name": "Sam"}, format="json")
    assert bad.status_code == 400
    assert api.get("/api/outreach/recruiters/?feed_item=99999").status_code == 400


# ---- #29 personalised, editable message (REQ-15) --------------------------------------

@pytest.mark.django_db
def test_draft_uses_posting_details_and_skills_and_can_be_edited(api):
    item = make_item(api.user)
    rid = {r["name"]: r["id"] for r in recruiters(api, item)}["Priya Sharma"]
    r = draft(api, rid)
    assert r.status_code == 201 and r.data["platform"] == "linkedin" and r.data["status"] == "draft"
    body = r.data["body"]
    assert "Priya" in body and "ML Engineer" in body and "Acme" in body and "Python" in body
    assert len(body) <= 300 and r.data["open_url"] == "https://www.linkedin.com/in/priya-sharma"
    edited = api.patch(f"/api/outreach/messages/{r.data['id']}/", {"body": "My own words."}, format="json")
    assert edited.status_code == 200 and edited.data["body"] == "My own words."
    too_long = api.patch(f"/api/outreach/messages/{r.data['id']}/", {"body": "x" * 301}, format="json")
    assert too_long.status_code == 400
    assert api.get("/api/outreach/messages/").data["count"] == 1


@pytest.mark.django_db
def test_draft_channel_choice_and_validation(api):
    item = make_item(api.user)
    ids = {r["name"]: r["id"] for r in recruiters(api, item)}
    assert draft(api, ids["@acme_hr"]).data["platform"] == "x"
    assert draft(api, ids["@acme_hr"], "linkedin").status_code == 400  # no LinkedIn profile
    assert draft(api, ids["Priya Sharma"], "x").status_code == 400  # no X handle
    assert draft(api, 99999).status_code == 400


@pytest.mark.django_db
def test_sent_message_cannot_be_edited(api, fake_x):
    item = make_item(api.user)
    rid = {r["name"]: r["id"] for r in recruiters(api, item)}["@acme_hr"]
    mid = draft(api, rid).data["id"]
    api.post(f"/api/outreach/messages/{mid}/send/")
    assert api.patch(f"/api/outreach/messages/{mid}/", {"body": "late"}, format="json").status_code == 409


# ---- #30 limits (REQ-16) --------------------------------------------------------------

@pytest.mark.django_db
def test_x_message_goes_through_the_api(api, fake_x):
    item = make_item(api.user)
    rid = {r["name"]: r["id"] for r in recruiters(api, item)}["@acme_hr"]
    mid = draft(api, rid).data["id"]
    r = api.post(f"/api/outreach/messages/{mid}/send/")
    assert r.status_code == 200 and r.data["status"] == "sent" and r.data["sent_at"]
    assert fake_x.sent[0][0] == "acme_hr" and "ML Engineer" in fake_x.sent[0][1]
    assert api.post(f"/api/outreach/messages/{mid}/send/").status_code == 409  # not twice


@pytest.mark.django_db
def test_linkedin_is_sent_by_the_user_and_then_marked(api, fake_x):
    item = make_item(api.user)
    rid = {r["name"]: r["id"] for r in recruiters(api, item)}["Priya Sharma"]
    msg = draft(api, rid).data
    assert api.post(f"/api/outreach/messages/{msg['id']}/send/").status_code == 400  # app never sends LinkedIn
    assert fake_x.sent == []
    r = api.post(f"/api/outreach/messages/{msg['id']}/mark-sent/")
    assert r.status_code == 200 and r.data["status"] == "sent"


@pytest.mark.django_db
def test_mark_sent_is_for_linkedin_only(api, fake_x):
    item = make_item(api.user)
    rid = {r["name"]: r["id"] for r in recruiters(api, item)}["@acme_hr"]
    mid = draft(api, rid).data["id"]
    assert api.post(f"/api/outreach/messages/{mid}/mark-sent/").status_code == 400


@pytest.mark.django_db
def test_default_limit_is_15_per_platform_and_over_it_is_blocked(api, fake_x):
    limits = {r["platform"]: r for r in api.get("/api/outreach/limits/").data}
    assert limits["x"]["daily_limit"] == limits["linkedin"]["daily_limit"] == 15
    api.put("/api/outreach/limits/", {"platform": "x", "daily_limit": 2}, format="json")
    results = []
    for i in range(3):
        item = make_item(api.user, ext=f"e{i}", platform="x", url=f"https://x.com/hr{i}/status/{i}",
                         description="Hiring")
        rid = recruiters(api, item)[0]["id"]
        api.patch(f"/api/outreach/messages/{draft(api, rid).data['id']}/", {"body": f"Unique text {i}"}, format="json")
        results.append(api.post(f"/api/outreach/messages/{OutreachMessage.objects.latest('id').pk}/send/"))
    assert [r.status_code for r in results] == [200, 200, 429]
    assert {r["platform"]: r for r in api.get("/api/outreach/limits/").data}["x"]["sent_today"] == 2
    assert api.put("/api/outreach/limits/", {"platform": "x", "daily_limit": -1}, format="json").status_code == 400
    assert api.put("/api/outreach/limits/", {"platform": "naukri", "daily_limit": 1}, format="json").status_code == 400


@pytest.mark.django_db
def test_linkedin_limit_is_separate_from_x(api, fake_x):
    api.put("/api/outreach/limits/", {"platform": "linkedin", "daily_limit": 0}, format="json")
    item = make_item(api.user)
    ids = {r["name"]: r["id"] for r in recruiters(api, item)}
    li = draft(api, ids["Priya Sharma"]).data["id"]
    assert api.post(f"/api/outreach/messages/{li}/mark-sent/").status_code == 429
    x = draft(api, ids["@acme_hr"]).data["id"]
    assert api.post(f"/api/outreach/messages/{x}/send/").status_code == 200


@pytest.mark.django_db
def test_x_api_failures(api, monkeypatch):
    item = make_item(api.user)
    rid = {r["name"]: r["id"] for r in recruiters(api, item)}["@acme_hr"]
    mid = draft(api, rid).data["id"]
    monkeypatch.setattr("outreach.services.get_x_messenger", lambda: FakeX(SubmitRateLimited("slow down")))
    assert api.post(f"/api/outreach/messages/{mid}/send/").status_code == 429
    monkeypatch.setattr("outreach.services.get_x_messenger", lambda: FakeX(SubmitError("rejected")))
    r = api.post(f"/api/outreach/messages/{mid}/send/")
    assert r.data["status"] == "failed" and r.data["detail"] == "rejected"
    assert api.get("/api/outreach/limits/").data[1]["sent_today"] == 0  # failures do not use the limit


@pytest.mark.django_db
def test_paused_messages_are_not_sent(api, fake_x):
    item = make_item(api.user)
    rid = {r["name"]: r["id"] for r in recruiters(api, item)}["@acme_hr"]
    mid = draft(api, rid).data["id"]
    assert api.patch(f"/api/outreach/messages/{mid}/", {"body": "  "}, format="json").status_code == 400
    api.post("/api/auth/pause/", {"paused": True}, format="json")
    assert api.post(f"/api/outreach/messages/{mid}/send/").status_code == 409
    assert fake_x.sent == []


# ---- #31 identical bulk messages (REQ-17) ---------------------------------------------

@pytest.mark.django_db
def test_same_text_to_a_second_recipient_is_rejected(api, fake_x):
    ids = []
    for i in range(3):
        item = make_item(api.user, ext=f"b{i}", platform="x", url=f"https://x.com/hr{i}/status/{i}",
                         description="Hiring")
        ids.append(draft(api, recruiters(api, item)[0]["id"]).data["id"])
    for mid in ids:
        api.patch(f"/api/outreach/messages/{mid}/", {"body": "Hi, I'd love to work with you."}, format="json")
    assert api.post(f"/api/outreach/messages/{ids[0]}/send/").status_code == 200
    second = api.post(f"/api/outreach/messages/{ids[1]}/send/")
    assert second.status_code == 409 and "already sent" in second.data["detail"]
    # case and spacing do not get around the check
    api.patch(f"/api/outreach/messages/{ids[2]}/", {"body": "  hi,  I'd LOVE to work with you."}, format="json")
    assert api.post(f"/api/outreach/messages/{ids[2]}/send/").status_code == 409
    # changing the text unblocks it
    api.patch(f"/api/outreach/messages/{ids[1]}/", {"body": "Hello, I admire your team."}, format="json")
    assert api.post(f"/api/outreach/messages/{ids[1]}/send/").status_code == 200
    assert len(fake_x.sent) == 2


@pytest.mark.django_db
def test_bulk_check_covers_linkedin_notes_and_other_users_are_unaffected(api, fake_x):
    from .conftest import make_user
    item = make_item(api.user)
    other_item = make_item(make_user("other@pes.edu"), ext="2")
    mine = draft(api, {r["name"]: r["id"] for r in recruiters(api, item)}["Priya Sharma"]).data
    api.patch(f"/api/outreach/messages/{mine['id']}/", {"body": "Same note"}, format="json")
    assert api.post(f"/api/outreach/messages/{mine['id']}/mark-sent/").status_code == 200
    # a different user may send the same words: the rule is per sender
    other_recruiter = Recruiter.objects.filter(posting=other_item.posting).first() or \
        __import__("outreach.services", fromlist=["x"]).suggest_recruiters(other_item.posting)[0]
    OutreachMessage.objects.create(user=other_item.user, recruiter=other_recruiter, platform="linkedin",
                                   body="Same note", status="draft")
    assert OutreachMessage.objects.filter(user=api.user).count() == 1


# ---- X adapter ------------------------------------------------------------------------

def test_x_messenger_sends_and_maps_errors(settings, monkeypatch):
    from types import SimpleNamespace as NS

    import tweepy

    from integrations.x_dm import XMessenger
    with pytest.raises(SubmitError, match="not configured"):
        XMessenger().send("hr", "hi")
    settings.X_API_KEY = settings.X_API_SECRET = settings.X_ACCESS_TOKEN = settings.X_ACCESS_SECRET = "k"

    class Client:
        mode = "ok"

        def __init__(self, **kw):
            pass

        def get_user(self, username):
            return NS(data=None if self.mode == "missing" else NS(id=7))

        def create_direct_message(self, participant_id, text):
            if self.mode == "limit":
                raise tweepy.TooManyRequests(NS(status_code=429, reason="Too Many", json=lambda: {}, text="", headers={}))
            if self.mode == "error":
                raise tweepy.TweepyException("boom")
            return NS(data={"dm_event_id": "42"})
    monkeypatch.setattr(tweepy, "Client", Client)
    assert XMessenger().send("@hr", "hi") == "42"
    for mode, exc in (("missing", SubmitError), ("limit", SubmitRateLimited), ("error", SubmitError)):
        Client.mode = mode
        with pytest.raises(exc):
            XMessenger().send("hr", "hi")
