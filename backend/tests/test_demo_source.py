"""Demo job source: recorded postings served through IJobSource so a demo feed is never empty."""
from integrations.base import SearchQuery
from integrations.demo import DemoJobSource, _load
from integrations.registry import get_source
from matching.models import FeedItem
from matching.services import run_search


def test_demo_data_covers_every_platform():
    platforms = {row["platform"] for row in _load()}
    assert platforms == {"linkedin", "naukri", "x"}


def test_demo_source_filters_by_role_and_platform():
    rows = DemoJobSource("linkedin").search(SearchQuery(roles=("Backend Engineer",)))
    assert rows and all(r.platform == "linkedin" for r in rows)
    assert all(r.external_id.startswith("demo-") for r in rows)
    assert any("Backend" in r.title for r in rows)


def test_registry_uses_demo_source_only_when_enabled(settings):
    settings.DEMO_SOURCES = True
    assert isinstance(get_source("naukri"), DemoJobSource)
    settings.DEMO_SOURCES = False
    assert not isinstance(get_source("naukri"), DemoJobSource)


def test_demo_search_fills_feed_and_dedupes_across_platforms(settings, user):
    settings.DEMO_SOURCES = True
    user.profile.preferred_roles = ["Backend Engineer"]
    user.profile.skills = ["Python", "Django", "PostgreSQL"]
    user.profile.save()

    result = run_search(user, platforms=["linkedin", "naukri", "x"])

    assert not result.errors
    assert result.new_feed_items > 0
    # Northwind Labs posts the same Django role on all three platforms.
    assert result.duplicates >= 1
    top = FeedItem.objects.filter(user=user, duplicate_of__isnull=True).first()
    assert top.relevance >= 60


def test_demo_postings_exercise_outreach_and_career_page_apply():
    from integrations.ats import detect_ats

    rows = _load()
    assert any("linkedin.com/in/" in r["description"] for r in rows)
    assert any(detect_ats(r["url"]) == "greenhouse" for r in rows)
    assert any(detect_ats(r["url"]) == "lever" for r in rows)
