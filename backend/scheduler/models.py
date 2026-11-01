from django.conf import settings
from django.db import models

from core.choices import Platform


class Schedule(models.Model):
    """REQ-18: one recurring search per user, mirrored into a Celery beat PeriodicTask."""

    class Cadence(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="schedule")
    cadence = models.CharField(max_length=10, choices=Cadence.choices, default=Cadence.DAILY)
    run_time = models.TimeField()
    weekday = models.PositiveSmallIntegerField(null=True, blank=True)  # 0 = Monday (weekly only)
    timezone = models.CharField(max_length=64, default="Asia/Kolkata")
    enabled = models.BooleanField(default=True)
    periodic_task = models.OneToOneField("django_celery_beat.PeriodicTask", null=True, blank=True,
                                         on_delete=models.SET_NULL, related_name="+")


class ScheduledRun(models.Model):
    """REQ-20: one row per search run, manual or scheduled."""

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        PARTIAL = "partial", "Partial"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    class Trigger(models.TextChoices):
        SCHEDULE = "schedule", "Schedule"
        MANUAL = "manual", "Manual"
        RETRY = "retry", "Deferred retry"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="runs")
    trigger = models.CharField(max_length=10, choices=Trigger.choices, default=Trigger.SCHEDULE)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING)
    platforms = models.JSONField(default=list)
    postings_found = models.PositiveIntegerField(default=0)
    new_matches = models.PositiveIntegerField(default=0)
    duplicates_hidden = models.PositiveIntegerField(default=0)
    applications_submitted = models.PositiveIntegerField(default=0)  # filled by Application Manager
    errors = models.JSONField(default=list)
    deferred = models.JSONField(default=dict)  # platform -> ISO retry time
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["user", "-started_at"], name="run_user_time_idx")]


class RateLimitWindow(models.Model):
    """REQ-19: action count for one user/platform/action in one fixed window."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    platform = models.CharField(max_length=20, choices=Platform.choices)
    action = models.CharField(max_length=30)
    window_start = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)
    exhausted_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "platform", "action", "window_start"],
                                               name="uniq_rate_window")]
