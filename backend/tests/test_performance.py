"""Issue #43 / SRS 6.1 checks that run in CI. The 50-user test is loadtest/run_degradation.py."""
import time

import pytest
from django.core.management import call_command

from matching.services import run_search

from .fakes import FakeSource, factory, posting


@pytest.mark.perf
@pytest.mark.django_db
def test_tc30_three_platform_search_finishes_within_30s_because_sources_run_in_parallel(user):
    # Each fake source takes 2 s, like a slow real site; serial would take 6 s.
    sources = {p: FakeSource(p, [posting(p, f"{p}{i}", title=f"ML Engineer {i}") for i in range(25)], delay=2)
               for p in ("linkedin", "naukri", "x")}
    start = time.perf_counter()
    result = run_search(user, source_factory=factory(sources))
    elapsed = time.perf_counter() - start
    assert sorted(result.platforms_searched) == ["linkedin", "naukri", "x"]
    assert result.postings_found == 75
    assert elapsed < 4.5, f"sources did not run in parallel ({elapsed:.1f}s)"
    assert elapsed < 30


@pytest.mark.perf
@pytest.mark.django_db
def test_slow_source_is_cut_off_so_search_stays_under_target(user, settings):
    settings.SOURCE_TIMEOUT_SECONDS = 0  # cutoff = timeout + 5 s
    sources = {"x": FakeSource("x", [posting("x", "1")]),
               "naukri": FakeSource("naukri", [posting("naukri", "2")], delay=8)}
    start = time.perf_counter()
    result = run_search(user, platforms=["x", "naukri"], source_factory=factory(sources))
    assert time.perf_counter() - start < 7
    assert result.platforms_searched == ["x"]
    assert {"platform": "naukri", "error": "Timed out."} in result.errors


@pytest.mark.perf
@pytest.mark.django_db
def test_feed_with_2000_items_responds_within_3s_and_uses_constant_queries(api, django_assert_max_num_queries):
    call_command("seed_loadtest", users=1, postings=2000, stdout=open("/dev/null", "w"))
    from django.contrib.auth import get_user_model
    from rest_framework_simplejwt.tokens import RefreshToken
    seeded = get_user_model().objects.get(email="load0@jobconnect.test")
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(seeded).access_token}")
    start = time.perf_counter()
    with django_assert_max_num_queries(6):  # no N+1: count, page, duplicates prefetch, auth
        r = api.get("/api/jobs/feed/?min_score=50&posted_within_days=14&location=bengal")
    assert r.status_code == 200 and r.json()["count"] > 0
    assert time.perf_counter() - start < 3
