"""Builds the configured IJobSource for a platform. New sources plug in here only (SRS 6.4)."""
from django.conf import settings

from .base import IJobSource, SourceError
from .demo import DemoJobSource
from .listings import LinkedInListingSource, NaukriListingSource, PoliteFetcher
from .x_source import XJobSource


def _fetcher() -> PoliteFetcher:
    return PoliteFetcher(
        user_agent=settings.COLLECTOR_USER_AGENT,
        min_delay=settings.COLLECTOR_MIN_DELAY_SECONDS,
        respect_robots=settings.COLLECTOR_RESPECT_ROBOTS,
        timeout=settings.SOURCE_TIMEOUT_SECONDS,
    )


def get_source(platform: str) -> IJobSource:
    if settings.DEMO_SOURCES and platform in ("x", "linkedin", "naukri"):
        return DemoJobSource(platform)
    if platform == "x":
        return XJobSource(settings.X_BEARER_TOKEN)
    if platform == "linkedin":
        return LinkedInListingSource(_fetcher())
    if platform == "naukri":
        return NaukriListingSource(_fetcher())
    raise SourceError(f"Unknown platform: {platform}")
