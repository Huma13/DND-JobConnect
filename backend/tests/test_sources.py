"""Issues #18, #19: X adapter and public listing collector."""
import json
from datetime import UTC
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests
import responses
import tweepy

from integrations.base import SearchQuery, SourceError, SourceRateLimited
from integrations.listings import (
    LINKEDIN_SEARCH_URL,
    LinkedInListingSource,
    NaukriListingSource,
    PoliteFetcher,
    parse_linkedin_cards,
    parse_naukri_json,
)
from integrations.x_source import MAX_QUERY_LEN, XJobSource, build_query

FIX = Path(__file__).parent / "fixtures"
Q = SearchQuery(roles=("ML Engineer",), locations=("Bengaluru",), max_results=10)


# ---- X / Tweepy (#18) -------------------------------------------------------

def tweet(id_, text, author_id=1):
    return SimpleNamespace(id=id_, text=text, author_id=author_id, created_at=None)


def x_client(tweets, users=()):
    client = MagicMock(spec=tweepy.Client)
    client.search_recent_tweets.return_value = SimpleNamespace(data=tweets, includes={"users": list(users)})
    return client


def test_x_query_targets_hiring_tags_and_excludes_retweets():
    q = build_query(Q)
    assert '"ML Engineer"' in q and "(#hiring OR #jobs)" in q and "-is:retweet" in q


def test_x_query_never_exceeds_api_v2_length_limit():
    q = build_query(SearchQuery(roles=tuple(f"Role number {i} with words" for i in range(60))))
    assert len(q) <= MAX_QUERY_LEN


def test_x_query_requires_a_role():
    with pytest.raises(SourceError):
        build_query(SearchQuery(roles=()))


def test_x_search_maps_tweets_to_postings():
    author = SimpleNamespace(id=1, name="Razorpay Careers", username="razorpaycareers")
    client = x_client([tweet(99, "We're hiring an ML Engineer at Razorpay! Location: Bengaluru #hiring")], [author])
    [p] = XJobSource("", client=client).search(Q)
    assert (p.platform, p.external_id, p.title, p.company, p.location) == \
        ("x", "99", "ML Engineer", "Razorpay", "Bengaluru")
    assert p.url == "https://x.com/razorpaycareers/status/99"
    kwargs = client.search_recent_tweets.call_args.kwargs
    assert 10 <= kwargs["max_results"] <= 100


def test_x_search_falls_back_to_author_name_for_company():
    author = SimpleNamespace(id=1, name="Acme HR", username="acme")
    [p] = XJobSource("", client=x_client([tweet(5, "ml engineer opening, DM us #jobs")], [author])).search(Q)
    assert p.company == "Acme HR"


def test_x_search_handles_empty_result():
    assert XJobSource("", client=x_client(None)).search(Q) == []


def test_x_rate_limit_becomes_source_rate_limited_with_reset_time():
    resp = requests.Response()
    resp.status_code = 429
    resp.headers["x-rate-limit-reset"] = "1893456000"
    client = MagicMock(spec=tweepy.Client)
    client.search_recent_tweets.side_effect = tweepy.TooManyRequests(resp)
    with pytest.raises(SourceRateLimited) as exc:
        XJobSource("", client=client).search(Q)
    assert exc.value.retry_at.tzinfo == UTC and exc.value.retry_at.year == 2030


def test_x_other_errors_become_source_error():
    client = MagicMock(spec=tweepy.Client)
    client.search_recent_tweets.side_effect = tweepy.TweepyException("boom")
    with pytest.raises(SourceError):
        XJobSource("", client=client).search(Q)


def test_x_requires_token():
    with pytest.raises(SourceError):
        XJobSource("")


# ---- LinkedIn / Naukri parsing against saved fixtures (#19) -----------------

def test_linkedin_fixture_parses_cards_and_skips_incomplete_ones():
    rows = parse_linkedin_cards((FIX / "linkedin_search.html").read_text())
    assert [r.external_id for r in rows] == ["4012345678", "4012399999"]
    first = rows[0]
    assert first.title == "ML Engineer" and first.company == "Razorpay"
    assert first.location.startswith("Bengaluru")
    assert first.url == "https://in.linkedin.com/jobs/view/ml-engineer-at-razorpay-4012345678"  # tracking stripped
    assert first.posted_at.date().isoformat() == "2026-10-28"


def test_naukri_fixture_parses_jobs():
    rows = parse_naukri_json(json.loads((FIX / "naukri_search.json").read_text()))
    assert len(rows) == 2
    ml = rows[0]
    assert ml.url.startswith("https://www.naukri.com/job-listings-")
    assert ml.location == "Bengaluru" and ml.skills == ["Python", "PyTorch", "MLOps", "SQL"]
    assert "1-3 Yrs" in ml.description and "<b>" not in ml.description


def test_naukri_tolerates_missing_job_list():
    assert parse_naukri_json({}) == []


# ---- Polite fetching: read-only, robots.txt, spacing, rate limits ----------

@responses.activate
def test_collector_only_issues_get_requests_and_identifies_itself():
    responses.get("https://www.linkedin.com/robots.txt", body="User-agent: *\nAllow: /")
    responses.get(LINKEDIN_SEARCH_URL, body=(FIX / "linkedin_search.html").read_text())
    src = LinkedInListingSource(PoliteFetcher("TestBot/1.0", min_delay=0))
    rows = src.search(Q)
    assert len(rows) == 2
    assert all(c.request.method == "GET" for c in responses.calls)
    assert all(c.request.headers["User-Agent"] == "TestBot/1.0" for c in responses.calls)


@responses.activate
def test_collector_refuses_paths_disallowed_by_robots_txt():
    responses.get("https://www.naukri.com/robots.txt", body="User-agent: *\nDisallow: /jobapi/")
    PoliteFetcher._robots.clear()
    with pytest.raises(SourceError, match="robots.txt"):
        NaukriListingSource(PoliteFetcher("TestBot/1.0", min_delay=0)).search(Q)
    assert len(responses.calls) == 1  # only robots.txt was fetched


@responses.activate
def test_collector_treats_unreachable_robots_as_disallowed():
    PoliteFetcher._robots.clear()
    responses.get("https://www.naukri.com/robots.txt", body=requests.ConnectionError("down"))
    with pytest.raises(SourceError):
        NaukriListingSource(PoliteFetcher("TestBot/1.0", min_delay=0)).search(Q)


@responses.activate
def test_collector_429_becomes_rate_limited():
    responses.get("https://www.naukri.com/jobapi/v3/search", status=429, headers={"Retry-After": "120"})
    fetcher = PoliteFetcher("TestBot/1.0", min_delay=0, respect_robots=False)
    with pytest.raises(SourceRateLimited) as exc:
        NaukriListingSource(fetcher).search(Q)
    assert exc.value.retry_at is not None


@responses.activate
def test_collector_http_error_and_bad_json():
    fetcher = PoliteFetcher("TestBot/1.0", min_delay=0, respect_robots=False)
    responses.get("https://www.naukri.com/jobapi/v3/search", status=503)
    with pytest.raises(SourceError, match="503"):
        NaukriListingSource(fetcher).search(Q)
    responses.replace(responses.GET, "https://www.naukri.com/jobapi/v3/search", body="<html>")
    with pytest.raises(SourceError, match="non-JSON"):
        NaukriListingSource(fetcher).search(Q)


@responses.activate
def test_naukri_search_end_to_end_with_fixture():
    responses.get("https://www.naukri.com/jobapi/v3/search", json=json.loads((FIX / "naukri_search.json").read_text()))
    rows = NaukriListingSource(PoliteFetcher("TestBot/1.0", min_delay=0, respect_robots=False)).search(Q)
    assert {r.external_id for r in rows} == {"281025500123", "281025500456"}
    assert responses.calls[0].request.headers["appid"] == "109"


def test_fetcher_spaces_requests_to_same_host(monkeypatch):
    sleeps = []
    monkeypatch.setattr("integrations.listings.time.sleep", sleeps.append)
    f = PoliteFetcher("TestBot/1.0", min_delay=5)
    PoliteFetcher._last_hit.clear()
    f._space("example.com")
    f._space("example.com")
    assert sleeps and 4 < sleeps[0] <= 5


def test_registry_builds_each_source(settings):
    from integrations.registry import get_source
    settings.X_BEARER_TOKEN = "token"
    assert {get_source(p).platform for p in ("x", "linkedin", "naukri")} == {"x", "linkedin", "naukri"}
    with pytest.raises(SourceError):
        get_source("myspace")
