"""X (Twitter) API v2 job source built on Tweepy (SRS 3.2, issue #18).

Uses the recent-search endpoint with an app bearer token. Posts tagged #hiring or
#jobs that mention one of the user's roles are turned into postings.
"""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

import tweepy

from .base import RawPosting, SearchQuery, SourceError, SourceRateLimited

log = logging.getLogger(__name__)

# API v2 recent search: 10..100 results per request, query length <= 512 chars.
MAX_PER_REQUEST = 100
MIN_PER_REQUEST = 10
MAX_QUERY_LEN = 512

_URL = re.compile(r"https?://\S+")
_HASHTAG = re.compile(r"#\w+")
_AT_COMPANY = re.compile(r"(?:\bat\s+|@)([A-Z][\w&.\-]*(?:\s+[A-Z][\w&.\-]*){0,3})")
_LOCATION = re.compile(r"(?:location|loc|based in|📍)\s*[:\-]?\s*([A-Z][A-Za-z ,/]{2,40})", re.I)


def build_query(query: SearchQuery) -> str:
    roles = [r.strip() for r in query.roles if r.strip()]
    if not roles:
        raise SourceError("At least one preferred role is required to search X.")
    tail = " (#hiring OR #jobs) -is:retweet -is:reply lang:en"
    parts: list[str] = []
    for role in roles:
        candidate = " OR ".join(parts + [f'"{role}"'])
        if len(f"({candidate}){tail}") > MAX_QUERY_LEN:
            break
        parts.append(f'"{role}"')
    if not parts:
        raise SourceError("Role text is too long for an X search query.")
    return f"({' OR '.join(parts)}){tail}"


def _first_line_title(text: str, roles: tuple[str, ...]) -> str:
    lower = text.lower()
    for role in roles:
        if role.lower() in lower:
            return role.strip()
    clean = _HASHTAG.sub("", _URL.sub("", text)).strip()
    return (clean.splitlines() or [""])[0][:120] or "Job post"


class XJobSource:
    platform = "x"

    def __init__(self, bearer_token: str, client: tweepy.Client | None = None):
        if not bearer_token and client is None:
            raise SourceError("X_BEARER_TOKEN is not configured.")
        self.client = client or tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=False)

    def search(self, query: SearchQuery) -> list[RawPosting]:
        q = build_query(query)
        per_request = max(MIN_PER_REQUEST, min(MAX_PER_REQUEST, query.max_results))
        try:
            resp = self.client.search_recent_tweets(
                query=q,
                max_results=per_request,
                tweet_fields=["created_at", "author_id", "entities"],
                expansions=["author_id"],
                user_fields=["name", "username"],
            )
        except tweepy.TooManyRequests as exc:
            reset = exc.response.headers.get("x-rate-limit-reset") if exc.response is not None else None
            retry_at = datetime.fromtimestamp(int(reset), tz=UTC) if reset else None
            raise SourceRateLimited("X API rate limit reached.", retry_at) from exc
        except tweepy.TweepyException as exc:
            raise SourceError(f"X API error: {exc}") from exc

        users = {u.id: u for u in (resp.includes or {}).get("users", [])}
        postings: list[RawPosting] = []
        for tweet in resp.data or []:
            author = users.get(tweet.author_id)
            company_match = _AT_COMPANY.search(tweet.text)
            loc_match = _LOCATION.search(tweet.text)
            company = company_match.group(1).strip() if company_match else (author.name if author else "Unknown")
            postings.append(RawPosting(
                platform=self.platform,
                external_id=str(tweet.id),
                url=f"https://x.com/{author.username if author else 'i/web'}/status/{tweet.id}",
                title=_first_line_title(tweet.text, query.roles),
                company=company,
                location=loc_match.group(1).strip().rstrip(",") if loc_match else "",
                description=tweet.text,
                posted_at=tweet.created_at,
            ))
        log.info("x_search query_len=%d results=%d", len(q), len(postings))
        return postings[: query.max_results]
