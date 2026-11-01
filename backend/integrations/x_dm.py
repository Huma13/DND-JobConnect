"""Send X direct messages through the API (issue #30). Needs user-context OAuth 1.0a credentials."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

import tweepy
from django.conf import settings

from .base import SubmitError, SubmitRateLimited

log = logging.getLogger(__name__)


class XMessenger:
    def _client(self) -> tweepy.Client:
        keys = (settings.X_API_KEY, settings.X_API_SECRET, settings.X_ACCESS_TOKEN, settings.X_ACCESS_SECRET)
        if not all(keys):
            raise SubmitError("X API credentials (X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET) "
                              "are not configured.")
        return tweepy.Client(consumer_key=keys[0], consumer_secret=keys[1],
                             access_token=keys[2], access_token_secret=keys[3])

    def send(self, handle: str, text: str) -> str:
        client = self._client()
        try:
            found = client.get_user(username=handle.lstrip("@"))
            if not found.data:
                raise SubmitError(f"X user @{handle.lstrip('@')} was not found.")
            sent = client.create_direct_message(participant_id=found.data.id, text=text)
        except tweepy.TooManyRequests as exc:
            raise SubmitRateLimited("X rate limit reached; try again later.") from exc
        except tweepy.TweepyException as exc:
            log.warning("X DM failed: %s", type(exc).__name__)
            raise SubmitError(f"X rejected the message: {type(exc).__name__}") from exc
        return str((sent.data or {}).get("dm_event_id", datetime.now(UTC).isoformat()))


def get_x_messenger() -> XMessenger:
    return XMessenger()
