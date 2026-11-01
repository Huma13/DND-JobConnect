"""Keeps each user's Schedule in sync with a django-celery-beat PeriodicTask (REQ-18)."""
import json

from django.db import transaction
from django_celery_beat.models import CrontabSchedule, PeriodicTask

TASK = "scheduler.tasks.scheduled_search"


def _cron_weekday(weekday: int) -> str:
    # Our API: 0 = Monday. Cron: 0 = Sunday.
    return str((weekday + 1) % 7)


@transaction.atomic
def sync(schedule) -> PeriodicTask | None:
    name = f"search-user-{schedule.user_id}"
    if not schedule.enabled:
        PeriodicTask.objects.filter(name=name).delete()
        return None
    crontab, _ = CrontabSchedule.objects.get_or_create(
        minute=str(schedule.run_time.minute),
        hour=str(schedule.run_time.hour),
        day_of_week="*" if schedule.cadence == "daily" else _cron_weekday(schedule.weekday),
        day_of_month="*",
        month_of_year="*",
        timezone=schedule.timezone,
    )
    task, _ = PeriodicTask.objects.update_or_create(
        name=name,
        defaults={"task": TASK, "crontab": crontab, "interval": None,
                  "args": json.dumps([schedule.user_id]), "enabled": True},
    )
    return task


def remove(user_id) -> None:
    PeriodicTask.objects.filter(name=f"search-user-{user_id}").delete()
