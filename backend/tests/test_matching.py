"""Issues #14 (REQ-5), #15 (REQ-6), #16 (REQ-7), #17 (REQ-8). TC-06..TC-09."""
from datetime import UTC, timedelta

import pytest
from django.utils import timezone

from integrations.base import SourceError, SourceRateLimited
from matching.dedup import dedup_key, normalize_company, normalize_title
from matching.models import FeedItem, JobPosting, SearchPreference
from matching.scoring import ProfileView, score
from matching.services import rescore_feed, run_search

from .conftest import make_user
from .fakes import FakeSource, factory, posting
from resume_parser.models import Profile

P = ProfileView(skills=("Python", "PyTorch", "SQL", "C++"), roles=("ML Engineer",),
                locations=("Bengaluru",), years=2)


# ---- REQ-6 scoring (TC-07) --------------------------------------------------

def test_tc07_scores_are_bounded_and_ordered_by_overlap():
    strong = score(P, "ML Engineer", "Razorpay", "Bengaluru", "Python, PyTorch, SQL. 1-3 years.")
    medium = score(P, "Machine Learning Engineer", "Infosys", "Pune", "Python and SQL. 2-4 years")
    weak = score(P, "Sales Executive", "Acme", "Delhi", "Field sales role, 5-8 years")
    assert 0 <= weak < medium < strong <= 100
    assert strong >= 85 and weak <= 10
    # abbreviations: 'ML Engineer' fully matches 'Machine Learning Engineer'
    assert medium >= 60


def test_score_perfect_and_zero_extremes():
    assert score(P, "ML Engineer Python PyTorch SQL C++", "", "Bengaluru", "2 years") == 100
    assert score(ProfileView((), (), (), 0), "", "", "", "") <= 15


def test_skill_matching_respects_word_boundaries():
    assert score(ProfileView(("C",), (), (), 0), "Clerk", "", "", "Customer care") == \
        score(ProfileView(("C",), (), (), 0), "Clerk", "", "", "nothing")
    assert score(ProfileView(("C++",), (), (), 0), "C++ developer", "", "", "") > \
        score(ProfileView(("C++",), (), (), 0), "C developer", "", "", "")


def test_remote_counts_as_location_match_and_experience_outside_range_is_penalised():
    remote = score(P, "ML Engineer", "X", "Remote", "Python")
    onsite_elsewhere = score(P, "ML Engineer", "X", "Delhi", "Python")
    assert remote > onsite_elsewhere
    assert score(P, "ML Engineer", "X", "Bengaluru", "8-12 years") < score(P, "ML Engineer", "X", "Bengaluru", "1-3 years")
    assert score(P, "ML Engineer", "X", "Bengaluru", "5+ years") < score(P, "ML Engineer", "X", "Bengaluru", "")


# ---- REQ-7 dedup (TC-08) ------------------------------------------------------

@pytest.mark.parametrize("a,b", [
    (("ML Engineer", "Razorpay"), ("ml engineer", "Razorpay Software Private Limited")),
    (("Sr. Backend Dev", "Swiggy"), ("Senior Backend Developer", "Swiggy Pvt Ltd")),
    (("Data Analyst (Urgent Hiring)", "Infosys Ltd."), ("Data Analyst", "INFOSYS LIMITED")),
])
def test_dedup_key_matches_same_role_and_company(a, b):
    assert dedup_key(*a) == dedup_key(*b)


def test_dedup_key_differs_for_different_roles_or_companies():
    assert dedup_key("ML Engineer", "Razorpay") != dedup_key("Data Engineer", "Razorpay")
    assert dedup_key("ML Engineer", "Razorpay") != dedup_key("ML Engineer", "Swiggy")
    assert normalize_company("Tech") == "tech"  # never collapses to empty
    assert normalize_title("SWE II") == "software engineer ii"


@pytest.mark.django_db
def test_tc08_same_job_on_linkedin_and_naukri_shows_once_marked_duplicate(api):
    sources = {"linkedin": FakeSource("linkedin", [posting("linkedin", "L1")]),
               "naukri": FakeSource("naukri", [posting("naukri", "N1", company="Razorpay Software Pvt Ltd")]),
               "x": FakeSource("x")}
    result = run_search(api.user, source_factory=factory(sources))
    assert (result.new_feed_items, result.duplicates) == (1, 1)
    feed = api.get("/api/jobs/feed/").json()["results"]
    assert len(feed) == 1
    assert feed[0]["is_duplicate"] is True
    assert len(feed[0]["also_on"]) == 1


@pytest.mark.django_db
def test_duplicates_across_runs_are_hidden(api):
    first = {"linkedin": FakeSource("linkedin", [posting("linkedin", "L1")])}
    run_search(api.user, platforms=["linkedin"], source_factory=factory(first))
    second = {"x": FakeSource("x", [posting("x", "T9", title="ml engineer")])}
    result = run_search(api.user, platforms=["x"], source_factory=factory(second))
    assert result.duplicates == 1 and result.new_feed_items == 0
    assert api.get("/api/jobs/feed/").json()["count"] == 1


@pytest.mark.django_db
def test_repeat_run_does_not_duplicate_feed_rows(user):
    src = {"linkedin": FakeSource("linkedin", [posting("linkedin", "L1")])}
    run_search(user, platforms=["linkedin"], source_factory=factory(src))
    run_search(user, platforms=["linkedin"], source_factory=factory(src))
    assert FeedItem.objects.filter(user=user).count() == 1
    assert JobPosting.objects.count() == 1


@pytest.mark.django_db
def test_feeds_are_private_per_user(api):
    other = make_user("other@pes.edu")
    run_search(other, platforms=["linkedin"],
               source_factory=factory({"linkedin": FakeSource("linkedin", [posting("linkedin", "L1")])}))
    assert api.get("/api/jobs/feed/").json()["count"] == 0
    other_item = FeedItem.objects.get(user=other)
    assert api.get(f"/api/jobs/feed/{other_item.pk}/").status_code == 404


# ---- REQ-5 source selection (TC-06) -------------------------------------------

@pytest.mark.django_db
def test_tc06_only_selected_sources_are_queried(api):
    resp = api.put("/api/jobs/preferences/", {"platforms": ["naukri", "x"]}, format="json")
    assert resp.status_code == 200 and resp.json()["platforms"] == ["naukri", "x"]
    sources = {p: FakeSource(p, [posting(p, p + "1", title=f"ML Engineer {p}")]) for p in ("linkedin", "naukri", "x")}
    result = run_search(api.user, source_factory=factory(sources))
    assert sorted(result.platforms_searched) == ["naukri", "x"]
    assert sources["linkedin"].calls == []


@pytest.mark.django_db
def test_source_preferences_are_validated(api):
    assert api.put("/api/jobs/preferences/", {"platforms": []}, format="json").status_code == 400
    assert api.put("/api/jobs/preferences/", {"platforms": ["indeed"]}, format="json").status_code == 400
    assert api.get("/api/jobs/preferences/").json()["platforms"] == ["linkedin", "x", "naukri"]


@pytest.mark.django_db
def test_failing_source_does_not_sink_the_run(user):
    sources = {"linkedin": FakeSource("linkedin", error=SourceError("blocked")),
               "naukri": FakeSource("naukri", error=RuntimeError("parser bug")),
               "x": FakeSource("x", [posting("x", "1")])}
    result = run_search(user, source_factory=factory(sources))
    assert result.platforms_searched == ["x"] and result.new_feed_items == 1
    assert {e["platform"] for e in result.errors} == {"linkedin", "naukri"}


@pytest.mark.django_db
def test_platform_rate_limit_is_recorded_as_deferred(user):
    from datetime import datetime
    retry = datetime(2030, 1, 1, tzinfo=UTC)
    result = run_search(user, platforms=["x"], source_factory=factory(
        {"x": FakeSource("x", error=SourceRateLimited("429", retry))}))
    assert result.deferred == {"x": retry}


@pytest.mark.django_db
def test_search_needs_a_preferred_role():
    u = make_user("norole@pes.edu", preferred_roles=[])
    assert run_search(u, source_factory=factory({})).errors[0]["platform"] == "*"


# ---- REQ-6 feed order + REQ-8 filters (TC-09) --------------------------------

@pytest.fixture
def seeded(api):
    now = timezone.now()
    rows = [
        posting("linkedin", "a", title="ML Engineer", location="Bengaluru", posted_at=now - timedelta(days=1)),
        posting("naukri", "b", title="Machine Learning Engineer", company="Infosys", location="Pune",
                posted_at=now - timedelta(days=2)),
        posting("x", "c", title="Sales Executive", company="Acme", location="Bengaluru",
                description="field sales", posted_at=now - timedelta(days=20)),
    ]
    by_platform = {p: FakeSource(p, [r for r in rows if r.platform == p]) for p in ("linkedin", "naukri", "x")}
    run_search(api.user, source_factory=factory(by_platform))
    return api


def scores(resp):
    return [r["relevance"] for r in resp.json()["results"]]


@pytest.mark.django_db
def test_feed_sorted_by_relevance_descending(seeded):
    s = scores(seeded.get("/api/jobs/feed/"))
    assert s == sorted(s, reverse=True) and len(s) == 3


@pytest.mark.django_db
def test_tc09_filters_combine(seeded):
    r = seeded.get("/api/jobs/feed/?platform=linkedin&platform=naukri&location=bengal&min_score=60&posted_within_days=7")
    results = r.json()["results"]
    assert [x["platform"] for x in results] == ["linkedin"]
    assert all(x["relevance"] >= 60 for x in results)


@pytest.mark.django_db
def test_individual_filters(seeded):
    assert {x["platform"] for x in seeded.get("/api/jobs/feed/?platform=x").json()["results"]} == {"x"}
    assert seeded.get("/api/jobs/feed/?posted_within_days=7").json()["count"] == 2
    assert seeded.get("/api/jobs/feed/?location=pune").json()["count"] == 1
    assert seeded.get("/api/jobs/feed/?min_score=101").status_code == 400
    assert seeded.get("/api/jobs/feed/?platform=orkut").status_code == 400


@pytest.mark.django_db
def test_recency_falls_back_to_first_seen_when_posting_has_no_date(api):
    run_search(api.user, platforms=["x"], source_factory=factory({"x": FakeSource("x", [posting("x", "nodate")])}))
    assert api.get("/api/jobs/feed/?posted_within_days=1").json()["count"] == 1


@pytest.mark.django_db
def test_skip_hides_item_unless_state_filter_used(seeded):
    item = seeded.get("/api/jobs/feed/").json()["results"][0]
    assert seeded.post(f"/api/jobs/feed/{item['id']}/skip/").status_code == 204
    assert seeded.get("/api/jobs/feed/").json()["count"] == 2
    assert seeded.get("/api/jobs/feed/?state=skipped").json()["count"] == 1


@pytest.mark.django_db
def test_profile_edit_rescores_feed(seeded):
    from resume_parser.models import Profile
    before = {i.pk: i.relevance for i in FeedItem.objects.filter(user=seeded.user)}
    Profile.objects.filter(user=seeded.user).update(preferred_roles=["Sales Executive"], skills=["sales"])
    assert rescore_feed(seeded.user) == 3
    after = {i.pk: i.relevance for i in FeedItem.objects.filter(user=seeded.user)}
    assert after != before


@pytest.mark.django_db
def test_feed_requires_auth(client):
    assert client.get("/api/jobs/feed/").status_code == 401


@pytest.mark.django_db
def test_preferences_created_with_all_platforms(user):
    from matching.services import selected_platforms
    assert set(selected_platforms(user)) == {"linkedin", "x", "naukri"}
    assert SearchPreference.objects.filter(user=user).count() == 1

# ---- Issue #42: New-user onboarding search validation ----------------

@pytest.mark.django_db
def test_onboarding_search_rejects_user_without_preferred_roles(api):
    profile = Profile.objects.get(user=api.user)
    profile.preferred_roles = []
    profile.save()

    response = api.post("/api/jobs/feed/search/")

    assert response.status_code == 400
    assert "preferred role" in response.json()["detail"].lower()


@pytest.mark.django_db
def test_onboarding_search_starts_with_completed_profile(api, monkeypatch):
    profile = Profile.objects.get(user=api.user)
    profile.skills = ["Python"]
    profile.preferred_roles = ["Software Developer"]
    profile.preferred_locations = ["Bengaluru"]
    profile.save()

    from matching import views

    queued = {}
    monkeypatch.setattr(
        views.search_task,
        "delay",
        lambda user_id, run_id=None: queued.update(
            user_id=user_id, run_id=run_id
        ),
    )

    response = api.post("/api/jobs/feed/search/")

    assert response.status_code == 202
    assert "run_id" in response.json()
    assert queued["user_id"] == api.user.pk