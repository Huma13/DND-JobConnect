"""REQ-19: hold actions back once a platform window reaches 90% of its limit.

Fixed windows aligned to the epoch. The counter row is locked with SELECT ... FOR UPDATE,
so concurrent workers can never both take the last slot.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone


@dataclass(frozen=True)
class Allowed:
    used: int
    limit: int


@dataclass(frozen=True)
class Deferred:
    retry_at: datetime
    used: int
    limit: int


def _window_start(now: datetime, seconds: int) -> datetime:
    epoch = int(now.timestamp())
    return datetime.fromtimestamp(epoch - epoch % seconds, tz=UTC)


def hold_threshold(limit: int) -> int:
    """Number of actions allowed before deferring: floor(90% of limit), at least 1."""
    return max(1, int(limit * settings.RATE_LIMIT_HOLD_RATIO))


def acquire(user, platform: str, action: str, now: datetime | None = None) -> Allowed | Deferred:
    from .models import RateLimitWindow

    limit, seconds = settings.RATE_LIMITS[platform][action]
    now = now or timezone.now()
    start = _window_start(now, seconds)
    for _ in range(2):  # retry once if two workers create the row at the same moment
        try:
            with transaction.atomic():
                row, _ = RateLimitWindow.objects.select_for_update().get_or_create(
                    user=user, platform=platform, action=action, window_start=start)
                if row.exhausted_until and row.exhausted_until > now:
                    return Deferred(row.exhausted_until, row.count, limit)
                if row.count >= hold_threshold(limit):
                    return Deferred(start + timedelta(seconds=seconds), row.count, limit)
                row.count += 1
                row.save(update_fields=["count"])
                return Allowed(row.count, limit)
        except IntegrityError:
            continue
    raise RuntimeError("Could not acquire rate-limit row")  # pragma: no cover


def mark_exhausted(user, platform: str, action: str, until: datetime, now: datetime | None = None) -> None:
    """The platform told us we are limited (HTTP 429): stop until its reset time."""
    from .models import RateLimitWindow

    _, seconds = settings.RATE_LIMITS[platform][action]
    now = now or timezone.now()
    RateLimitWindow.objects.update_or_create(
        user=user, platform=platform, action=action, window_start=_window_start(now, seconds),
        defaults={"exhausted_until": until})


def usage(user) -> list[dict]:
    from .models import RateLimitWindow

    now = timezone.now()
    out = []
    for platform, actions in settings.RATE_LIMITS.items():
        for action, (limit, seconds) in actions.items():
            row = RateLimitWindow.objects.filter(user=user, platform=platform, action=action,
                                                 window_start=_window_start(now, seconds)).first()
            used = row.count if row else 0
            out.append({"platform": platform, "action": action, "used": used, "limit": limit,
                        "hold_at": hold_threshold(limit), "held": used >= hold_threshold(limit),
                        "window_resets_at": _window_start(now, seconds) + timedelta(seconds=seconds)})
    return out
