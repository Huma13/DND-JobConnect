"""Issues #32 (REQ-18), #33 (REQ-19), #34 (REQ-20), SRS 6.2. TC-19, TC-20, TC-21, TC-29."""
import json
import threading
from datetime import UTC, datetime, timedelta

import pytest
from django.core import mail
from django.db import connection
from django_celery_beat.models import PeriodicTask

from applications.models import Notification
from integrations.base import SourceError
from scheduler.models import RateLimitWindow, Schedule, ScheduledRun
from scheduler.ratelimit import Allowed, Deferred, acquire, hold_threshold, mark_exhausted
from scheduler.tasks import execute_run, scheduled_search, search_task

from .conftest import make_user
from .fakes import FakeSource, factory, posting

NOW = datetime(2026, 11, 2, 10, 0, 30, tzinfo=UTC)


# ---- REQ-18 schedules (TC-19) ---------------------------------------------------

@pytest.mark.django_db
def test_tc19_daily_schedule_creates_celery_beat_entry(api):
    r = api.put("/api/scheduler/schedule/", {"cadence": "daily", "run_time": "09:00"}, format="json")
    assert r.status_code == 201
    task = PeriodicTask.objects.get(name=f"search-user-{api.user.pk}")
    assert task.task == "scheduler.tasks.scheduled_search" and task.enabled
    assert json.loads(task.args) == [api.user.pk]
    assert (task.crontab.hour, task.crontab.minute, task.crontab.day_of_week) == ("9", "0", "*")
    assert str(task.crontab.timezone) == "Asia/Kolkata"


@pytest.mark.django_db
def test_tc19_beat_entry_actually_fires_at_the_scheduled_time(api):
    api.put("/api/scheduler/schedule/", {"cadence": "daily", "run_time": "09:00"}, format="json")
    sched = PeriodicTask.objects.get(name=f"search-user-{api.user.pk}").crontab.schedule
    from zoneinfo import ZoneInfo
    ist = ZoneInfo("Asia/Kolkata")
    due, _ = sched.is_due(datetime(2026, 11, 1, 9, 0, tzinfo=ist) - timedelta(days=1))
    assert due  # last run yesterday 09:00 -> due again
    assert sched.remaining_estimate(datetime(2026, 11, 1, 8, 59, tzinfo=ist)) <= timedelta(minutes=1)


@pytest.mark.django_db
def test_weekly_schedule_maps_monday_to_cron_weekday(api):
    r = api.put("/api/scheduler/schedule/", {"cadence": "weekly", "run_time": "18:30", "weekday": 0}, format="json")
    assert r.status_code == 201
    cron = PeriodicTask.objects.get().crontab
    assert (cron.day_of_week, cron.hour, cron.minute) == ("1", "18", "30")


@pytest.mark.django_db
def test_schedule_validation(api):
    assert api.put("/api/scheduler/schedule/", {"cadence": "weekly", "run_time": "09:00"}, format="json").status_code == 400
    assert api.put("/api/scheduler/schedule/", {"cadence": "weekly", "run_time": "09:00", "weekday": 7},
                   format="json").status_code == 400
    assert api.put("/api/scheduler/schedule/", {"cadence": "daily", "run_time": "09:00", "timezone": "Mars/Base"},
                   format="json").status_code == 400
    assert api.get("/api/scheduler/schedule/").status_code == 404


@pytest.mark.django_db
def test_schedule_update_disable_and_delete(api):
    api.put("/api/scheduler/schedule/", {"cadence": "daily", "run_time": "09:00"}, format="json")
    r = api.put("/api/scheduler/schedule/", {"cadence": "daily", "run_time": "07:15"}, format="json")
    assert r.status_code == 200 and api.get("/api/scheduler/schedule/").json()["run_time"] == "07:15:00"
    assert PeriodicTask.objects.get().crontab.hour == "7"
    api.put("/api/scheduler/schedule/", {"cadence": "daily", "run_time": "07:15", "enabled": False}, format="json")
    assert not PeriodicTask.objects.exists()
    api.put("/api/scheduler/schedule/", {"cadence": "daily", "run_time": "07:15"}, format="json")
    assert api.delete("/api/scheduler/schedule/").status_code == 204
    assert not PeriodicTask.objects.exists() and not Schedule.objects.exists()


@pytest.mark.django_db
def test_deleting_user_removes_beat_entry(api):
    api.put("/api/scheduler/schedule/", {"cadence": "daily", "run_time": "09:00"}, format="json")
    api.user.delete()
    assert not PeriodicTask.objects.exists()


# ---- REQ-19 rate limits (TC-20) ------------------------------------------------

@pytest.mark.django_db
def test_tc20_actions_deferred_at_90_percent_of_window(user, settings):
    settings.RATE_LIMITS = {"x": {"search": (10, 900)}}
    results = [acquire(user, "x", "search", now=NOW) for _ in range(10)]
    allowed = [r for r in results if isinstance(r, Allowed)]
    deferred = [r for r in results if isinstance(r, Deferred)]
    assert len(allowed) == 9 == hold_threshold(10) and len(deferred) == 1
    window_end = datetime(2026, 11, 2, 10, 15, tzinfo=UTC)
    assert deferred[0].retry_at == window_end  # pushed to the next window
    assert isinstance(acquire(user, "x", "search", now=window_end + timedelta(seconds=1)), Allowed)


@pytest.mark.django_db
def test_windows_are_per_user_and_platform(user, settings):
    settings.RATE_LIMITS = {"x": {"search": (2, 900)}, "naukri": {"search": (2, 900)}}
    other = make_user("b@pes.edu")
    assert isinstance(acquire(user, "x", "search", now=NOW), Allowed)
    assert isinstance(acquire(user, "x", "search", now=NOW), Deferred)  # 90% of 2 -> 1
    assert isinstance(acquire(user, "naukri", "search", now=NOW), Allowed)
    assert isinstance(acquire(other, "x", "search", now=NOW), Allowed)


@pytest.mark.django_db
def test_platform_429_blocks_until_reset(user):
    until = NOW + timedelta(minutes=5)
    mark_exhausted(user, "x", "search", until, now=NOW)
    d = acquire(user, "x", "search", now=NOW + timedelta(minutes=1))
    assert isinstance(d, Deferred) and d.retry_at == until


@pytest.mark.django_db(transaction=True)
def test_concurrent_workers_never_exceed_the_hold_threshold(settings):
    if connection.vendor != "postgresql":
        pytest.skip("row locking needs PostgreSQL")
    settings.RATE_LIMITS = {"x": {"search": (20, 900)}}
    user = make_user("race@pes.edu")
    results, lock = [], threading.Lock()

    def worker():
        from django.db import connection as c
        try:
            for _ in range(5):
                r = acquire(user, "x", "search", now=NOW)
                with lock:
                    results.append(r)
        finally:
            c.close()

    threads = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sum(isinstance(r, Allowed) for r in results) == hold_threshold(20) == 18
    assert RateLimitWindow.objects.get().count == 18


@pytest.mark.django_db
def test_run_search_defers_platform_at_limit_without_calling_it(user, settings):
    settings.RATE_LIMITS = {"x": {"search": (1, 900)}, "naukri": {"search": (30, 3600)}}
    acquire(user, "x", "search")  # uses the only slot
    sources = {"x": FakeSource("x", [posting("x", "1")]), "naukri": FakeSource("naukri", [posting("naukri", "2")])}
    from matching.services import run_search
    result = run_search(user, platforms=["x", "naukri"], source_factory=factory(sources))
    assert "x" in result.deferred and sources["x"].calls == []
    assert result.platforms_searched == ["naukri"]


@pytest.mark.django_db
def test_rate_limit_usage_endpoint(api):
    acquire(api.user, "x", "search")
    rows = {r["platform"]: r for r in api.get("/api/scheduler/rate-limits/").json()}
    assert rows["x"]["used"] == 1 and rows["x"]["hold_at"] == 54 and rows["x"]["held"] is False


# ---- REQ-20 run log (TC-21), Pause All (TC-29) --------------------------------

def patch_sources(monkeypatch, sources):
    monkeypatch.setattr("matching.services.get_source", factory(sources))
    import matching.services as ms
    monkeypatch.setattr(ms.run_search, "__defaults__", (None, factory(sources), None))


@pytest.mark.django_db
def test_tc21_completed_run_logs_found_matches_and_errors(api, monkeypatch):
    patch_sources(monkeypatch, {
        "linkedin": FakeSource("linkedin", [posting("linkedin", "1"), posting("linkedin", "2", title="Data Scientist")]),
        "naukri": FakeSource("naukri", [posting("naukri", "3")]),  # duplicate of linkedin/1
        "x": FakeSource("x", error=SourceError("X_BEARER_TOKEN is not configured.")),
    })
    run_id = scheduled_search(api.user.pk)
    run = api.get(f"/api/scheduler/runs/{run_id}/").json()
    assert run["trigger"] == "schedule" and run["status"] == "partial"
    assert (run["postings_found"], run["new_matches"], run["duplicates_hidden"]) == (3, 2, 1)
    assert run["errors"] == [{"platform": "x", "error": "X_BEARER_TOKEN is not configured."}]
    assert run["finished_at"] and sorted(run["platforms"]) == ["linkedin", "naukri"]
    assert api.get("/api/scheduler/runs/").json()["count"] == 1


@pytest.mark.django_db
def test_successful_and_failed_run_status(user, monkeypatch):
    patch_sources(monkeypatch, {p: FakeSource(p, [posting(p, p)]) for p in ("linkedin", "x", "naukri")})
    assert ScheduledRun.objects.get(pk=search_task(user.pk)).status == "success"
    patch_sources(monkeypatch, {p: FakeSource(p, error=SourceError("down")) for p in ("linkedin", "x", "naukri")})
    assert ScheduledRun.objects.get(pk=search_task(user.pk)).status == "failed"


@pytest.mark.django_db
def test_crashing_run_is_marked_failed(user, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db gone")
    monkeypatch.setattr("matching.services.run_search", boom)
    run = ScheduledRun.objects.create(user=user)
    with pytest.raises(RuntimeError):
        execute_run(run)
    run.refresh_from_db()
    assert run.status == "failed" and run.finished_at


@pytest.mark.django_db
def test_run_logs_are_private(api):
    other = make_user("o@pes.edu")
    run = ScheduledRun.objects.create(user=other)
    assert api.get(f"/api/scheduler/runs/{run.pk}/").status_code == 404


@pytest.mark.django_db
def test_tc29_pause_all_skips_scheduled_run(api, monkeypatch):
    src = FakeSource("x", [posting("x", "1")])
    patch_sources(monkeypatch, {"x": src, "linkedin": src, "naukri": src})
    assert api.post("/api/auth/pause/", {"paused": True}, format="json").json()["automation_paused"] is True
    run = ScheduledRun.objects.get(pk=scheduled_search(api.user.pk))
    assert run.status == "skipped" and src.calls == []
    assert api.post("/api/jobs/feed/search/").status_code == 409


@pytest.mark.django_db
def test_tc29_pause_during_run_stops_storing_results(user, monkeypatch):
    paused = {"value": False}
    monkeypatch.setattr("scheduler.tasks._paused", lambda _uid: paused["value"])

    class PausingSource(FakeSource):
        def search(self, query):  # user presses Pause All while the source is being queried
            paused["value"] = True
            return super().search(query)

    patch_sources(monkeypatch, {"x": PausingSource("x", [posting("x", "1")])})
    run = ScheduledRun.objects.create(user=user)
    execute_run(run, platforms=["x"])
    run.refresh_from_db()
    assert run.new_matches == 0 and "paused" in run.errors[0]["error"]


@pytest.mark.django_db
def test_manual_search_endpoint_runs_and_blocks_concurrent_runs(api, monkeypatch):
    patch_sources(monkeypatch, {p: FakeSource(p, [posting(p, p)]) for p in ("linkedin", "x", "naukri")})
    r = api.post("/api/jobs/feed/search/")
    assert r.status_code == 202
    assert ScheduledRun.objects.get(pk=r.json()["run_id"]).status == "success"
    ScheduledRun.objects.create(user=api.user)  # still running
    assert api.post("/api/jobs/feed/search/").status_code == 409


@pytest.mark.django_db
def test_finished_run_is_never_reexecuted(user, monkeypatch):
    src = FakeSource("x", [posting("x", "1")])
    patch_sources(monkeypatch, {"x": src, "linkedin": src, "naukri": src})
    run = ScheduledRun.objects.create(user=user, status="success")
    assert search_task(user.pk, run_id=run.pk) == run.pk and src.calls == []
    assert search_task(999999) is None


@pytest.mark.django_db
def test_deferred_platforms_are_requeued_for_window_reset(user, monkeypatch, settings, django_capture_on_commit_callbacks):
    settings.RATE_LIMITS = {"x": {"search": (1, 900)}}
    acquire(user, "x", "search")
    queued = []
    monkeypatch.setattr("scheduler.tasks.search_task.apply_async", lambda **kw: queued.append(kw))
    patch_sources(monkeypatch, {"x": FakeSource("x", [posting("x", "1")])})
    with django_capture_on_commit_callbacks(execute=True):
        run = execute_run(ScheduledRun.objects.create(user=user), platforms=["x"])
    assert run.status == "partial" and "x" in run.deferred
    assert queued and queued[0]["kwargs"]["platforms"] == ["x"] and queued[0]["eta"]


@pytest.mark.django_db
def test_health_endpoint(client):
    assert client.get("/health/").json() == {"status": "ok"}


@pytest.mark.django_db
def test_register_and_login(client):
    assert client.post("/api/auth/register/", {"email": "n@pes.edu", "password": "Str0ng!pass9"}).status_code == 201
    assert "access" in client.post("/api/auth/login/", {"email": "n@pes.edu", "password": "Str0ng!pass9"}).json()

# ---- Issue #40: Email and In-App Notifications -------------------------------

@pytest.mark.django_db
def test_successful_run_sends_new_match_and_run_result_notifications(
    user, monkeypatch, settings, django_capture_on_commit_callbacks
):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.DEFAULT_FROM_EMAIL = "notifications@test.com"

    patch_sources(
        monkeypatch,
        {
            p: FakeSource(p, [posting(p, p)])
            for p in ("linkedin", "x", "naukri")
        },
    )

    with django_capture_on_commit_callbacks(execute=True):
        search_task(user.pk)

    kinds = list(
        Notification.objects.filter(user=user)
        .values_list("kind", flat=True)
    )

    assert "new_matches" in kinds
    assert "run_result" in kinds
    assert len(mail.outbox) == 2


@pytest.mark.django_db
def test_failed_run_sends_run_result_notification(
    user, monkeypatch, settings, django_capture_on_commit_callbacks
):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.DEFAULT_FROM_EMAIL = "notifications@test.com"

    patch_sources(
        monkeypatch,
        {
            p: FakeSource(p, error=SourceError("down"))
            for p in ("linkedin", "x", "naukri")
        },
    )

    with django_capture_on_commit_callbacks(execute=True):
        run_id = search_task(user.pk)
    run = ScheduledRun.objects.get(pk=run_id)

    assert run.status == "failed"
    assert Notification.objects.filter(
        user=user,
        kind="run_result",
    ).exists()
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_paused_run_sends_skipped_notification(
    user, settings, django_capture_on_commit_callbacks
):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.DEFAULT_FROM_EMAIL = "notifications@test.com"

    user.automation_paused = True
    user.save(update_fields=["automation_paused"])

    with django_capture_on_commit_callbacks(execute=True):
        run_id = search_task(user.pk)

    run = ScheduledRun.objects.get(pk=run_id)

    assert run.status == "skipped"
    assert Notification.objects.filter(
        user=user,
        kind="run_result",
    ).exists()
    assert len(mail.outbox) == 1
