"""Demo job source: serves recorded postings from a JSON file instead of the live sites.

LinkedIn's and Naukri's robots.txt disallow the public listing paths and X search needs a paid
token, so a live demo would show an empty feed. With DEMO_SOURCES=1 every platform is served
from demo_data/postings.json through the same IJobSource interface, so a search still runs the
real pipeline: rate limiter -> source -> scoring -> de-duplication -> feed.
"""
from __future__ import annotations

import json
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

from django.utils import timezone

from .base import RawPosting, SearchQuery

DATA_FILE = Path(__file__).parent / "demo_data" / "postings.json"


@lru_cache(maxsize=1)
def _load() -> list[dict]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def _matches(row: dict, query: SearchQuery) -> bool:
    if not query.roles:
        return True
    text = f"{row['title']} {row.get('description', '')}".lower()
    words = {w for role in query.roles for w in role.lower().split() if len(w) > 2}
    return any(w in text for w in words)


class DemoJobSource:
    def __init__(self, platform: str):
        self.platform = platform

    def search(self, query: SearchQuery) -> list[RawPosting]:
        now = timezone.now()
        rows = [r for r in _load() if r["platform"] == self.platform and _matches(r, query)]
        return [
            RawPosting(
                platform=self.platform,
                external_id=f"demo-{r['id']}",
                url=r["url"],
                title=r["title"],
                company=r["company"],
                location=r.get("location", ""),
                description=r.get("description", ""),
                posted_at=now - timedelta(days=r.get("days_ago", 1)),
                skills=r.get("skills", []),
            )
            for r in rows[: query.max_results]
        ]
