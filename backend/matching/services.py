"""Job Aggregation & Matching (SAD): collect, score, dedupe (REQ-5..7)."""
from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from datetime import datetime

from django.conf import settings
from django.db import transaction

from integrations.base import IJobSource, RawPosting, SearchQuery, SourceError, SourceRateLimited
from integrations.registry import get_source
from resume_parser.models import Profile
from scheduler.ratelimit import Deferred, acquire, mark_exhausted

from .dedup import dedup_key
from .models import FeedItem, JobPosting, SearchPreference
from .scoring import ProfileView, score

log = logging.getLogger(__name__)


@dataclass
class SearchResult:
    platforms_searched: list[str] = field(default_factory=list)
    postings_found: int = 0
    new_feed_items: int = 0
    duplicates: int = 0
    errors: list[dict] = field(default_factory=list)
    deferred: dict[str, datetime] = field(default_factory=dict)


def selected_platforms(user) -> list[str]:
    """REQ-5: only the sources the user picked."""
    pref, _ = SearchPreference.objects.get_or_create(user=user)
    return list(pref.platforms)


def profile_view(user) -> ProfileView:
    profile = Profile.objects.filter(user=user).first()
    if profile is None:
        return ProfileView((), (), (), 0)
    return ProfileView(
        skills=tuple(profile.skills), roles=tuple(profile.preferred_roles),
        locations=tuple(profile.preferred_locations), years=profile.years_of_experience,
    )


def _store(user, view: ProfileView, raws: list[RawPosting], result: SearchResult) -> None:
    for raw in raws:
        key = dedup_key(raw.title, raw.company)
        with transaction.atomic():
            posting, _ = JobPosting.objects.update_or_create(
                platform=raw.platform, external_id=raw.external_id,
                defaults=dict(url=raw.url[:1000], title=raw.title[:300], company=raw.company[:300],
                              location=raw.location[:300], description=raw.description,
                              skills=raw.skills, posted_at=raw.posted_at, dedup_key=key),
            )
            if FeedItem.objects.filter(user=user, posting=posting).exists():
                continue
            canonical = (FeedItem.objects.select_for_update()
                         .filter(user=user, posting__dedup_key=key, duplicate_of__isnull=True)
                         .order_by("created_at").first())
            relevance = score(view, raw.title, raw.company, raw.location, raw.description, raw.skills)
            FeedItem.objects.create(user=user, posting=posting, relevance=relevance, duplicate_of=canonical)
            if canonical:
                result.duplicates += 1
                if relevance > canonical.relevance:
                    canonical.relevance = relevance
                    canonical.save(update_fields=["relevance"])
            else:
                result.new_feed_items += 1


def run_search(user, platforms: list[str] | None = None,
               source_factory: Callable[[str], IJobSource] = get_source,
               should_stop: Callable[[], bool] | None = None) -> SearchResult:
    view = profile_view(user)
    result = SearchResult()
    if not view.roles:
        result.errors.append({"platform": "*", "error": "Add at least one preferred role to your profile."})
        return result
    query = SearchQuery(roles=view.roles[:5], locations=view.locations[:3])
    wanted = [p for p in (platforms or selected_platforms(user)) if p in settings.RATE_LIMITS]

    runnable = []
    for platform in wanted:
        decision = acquire(user, platform, "search")
        if isinstance(decision, Deferred):
            result.deferred[platform] = decision.retry_at
        else:
            runnable.append(platform)

    # Sources run in parallel so a 3-platform search fits the 30 s target (SRS 6.1).
    pool = ThreadPoolExecutor(max_workers=max(1, len(runnable)))
    try:
        futures = {pool.submit(lambda p=p: source_factory(p).search(query)): p for p in runnable}
        try:
            completed = list(as_completed(futures, timeout=settings.SOURCE_TIMEOUT_SECONDS + 5))
        except FuturesTimeout:
            completed = [f for f in futures if f.done()]
            for fut, platform in futures.items():
                if not fut.done():
                    fut.cancel()
                    result.errors.append({"platform": platform, "error": "Timed out."})
        for fut in completed:
            platform = futures[fut]
            try:
                raws = fut.result()
            except SourceRateLimited as exc:
                result.deferred[platform] = exc.retry_at
                if exc.retry_at:
                    mark_exhausted(user, platform, "search", exc.retry_at)
                result.errors.append({"platform": platform, "error": str(exc)})
                continue
            except SourceError as exc:
                result.errors.append({"platform": platform, "error": str(exc)})
                continue
            except Exception as exc:  # a broken adapter must not sink the whole run
                log.exception("source %s crashed", platform)
                result.errors.append({"platform": platform, "error": f"Unexpected error: {type(exc).__name__}"})
                continue
            if should_stop and should_stop():
                result.errors.append({"platform": platform, "error": "Stopped: automation paused."})
                continue
            result.platforms_searched.append(platform)
            result.postings_found += len(raws)
            _store(user, view, raws, result)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return result


def rescore_feed(user) -> int:
    """Called after a profile edit (REQ-3) so rankings reflect the new profile."""
    view = profile_view(user)
    items = list(FeedItem.objects.filter(user=user).select_related("posting"))
    for item in items:
        p = item.posting
        item.relevance = score(view, p.title, p.company, p.location, p.description, p.skills)
    FeedItem.objects.bulk_update(items, ["relevance"], batch_size=500)
    return len(items)
