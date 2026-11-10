"""Issue #12 over the API: JWT works and inputs default to the user's profile and feed."""
from matching.models import FeedItem, JobPosting


def _posting(n, description):
    return JobPosting.objects.create(platform="naukri", external_id=f"t-{n}", url=f"https://e.com/{n}",
                                     title="ML Engineer", company=f"Co{n}", description=description,
                                     dedup_key=f"k{n}")


def test_tips_need_authentication(client, db):
    assert client.post("/api/resume/tips/", {}, content_type="application/json").status_code == 401


def test_tips_default_to_profile_and_feed(api, user):
    for n in range(3):
        FeedItem.objects.create(user=user, posting=_posting(n, "Kubernetes and Python required"), relevance=80)
    resp = api.post("/api/resume/tips/", {}, format="json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["target_role"] == "ML Engineer"
    assert body["postings_analyzed"] == 3
    assert "kubernetes" in [k["keyword"].lower() for k in body["missing_keywords"]]


def test_tips_explicit_input_overrides_defaults(api):
    resp = api.post("/api/resume/tips/", {"target_role": "Data Analyst", "postings": ["Tableau and SQL"] * 2,
                                          "resume_text": "SQL"}, format="json")
    assert resp.status_code == 200
    assert resp.json()["target_role"] == "Data Analyst"


def test_tips_reject_bad_postings(api):
    assert api.post("/api/resume/tips/", {"postings": "nope"}, format="json").status_code == 400
