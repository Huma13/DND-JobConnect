"""Celery tasks for scheduled and manual searches (REQ-18, REQ-19, REQ-20, SRS 6.2)."""
import logging

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from accounts.gates import DISCLAIMER_REQUIRED, disclaimer_accepted

from .models import ScheduledRun

log = logging.getLogger(__name__)


def _paused(user_id) -> bool:
    return get_user_model().objects.filter(pk=user_id, automation_paused=True).exists()


def execute_run(run: ScheduledRun, platforms=None) -> ScheduledRun:
    from matching.services import run_search

    user = run.user
    if user.automation_paused:
        run.status = ScheduledRun.Status.SKIPPED
        run.errors = [{"platform": "*", "error": "Automation is paused."}]
        run.finished_at = timezone.now()
        run.save()
        return run
    if not disclaimer_accepted(user):
        run.status = ScheduledRun.Status.SKIPPED
        run.errors = [{"platform": "*", "error": DISCLAIMER_REQUIRED}]
        run.finished_at = timezone.now()
        run.save()
        return run
    try:
        result = run_search(user, platforms=platforms, should_stop=lambda: _paused(user.pk))
    except Exception as exc:
        log.exception("run %s failed", run.pk)
        run.status = ScheduledRun.Status.FAILED
        run.errors = [{"platform": "*", "error": f"Run failed: {type(exc).__name__}"}]
        run.finished_at = timezone.now()
        run.save()
        raise
    run.platforms = result.platforms_searched
    run.postings_found = result.postings_found
    run.new_matches = result.new_feed_items
    run.duplicates_hidden = result.duplicates
    run.errors = result.errors
    run.deferred = {p: t.isoformat() for p, t in result.deferred.items() if t}
    if not result.errors and not result.deferred:
        run.status = ScheduledRun.Status.SUCCESS
    elif result.platforms_searched:
        run.status = ScheduledRun.Status.PARTIAL
    elif result.deferred:
        run.status = ScheduledRun.Status.PARTIAL  # nothing failed; work is queued for the next window
    else:
        run.status = ScheduledRun.Status.FAILED
    run.finished_at = timezone.now()
    run.save()

    # REQ-19: deferred platforms are retried when their window resets.
    for platform, retry_at in result.deferred.items():
        if retry_at:
            transaction.on_commit(lambda p=platform, t=retry_at: search_task.apply_async(
                args=[user.pk], kwargs={"platforms": [p], "trigger": ScheduledRun.Trigger.RETRY}, eta=t))
    return run


@shared_task(acks_late=True)
def search_task(user_id, platforms=None, trigger=ScheduledRun.Trigger.MANUAL, run_id=None):
    user = get_user_model().objects.filter(pk=user_id).first()
    if user is None:
        return None
    run = (ScheduledRun.objects.filter(pk=run_id, user=user).first() if run_id
           else ScheduledRun.objects.create(user=user, trigger=trigger))
    if run is None or run.status != ScheduledRun.Status.RUNNING:
        return run.pk if run else None  # idempotent: never re-execute a finished run
    return execute_run(run, platforms).pk


@shared_task(acks_late=True)
def scheduled_search(user_id):
    return search_task.run(user_id, trigger=ScheduledRun.Trigger.SCHEDULE)
