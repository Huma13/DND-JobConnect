"""Read-only collector for public LinkedIn and Naukri job listings (SRS 3.2, issue #19).

Compliance rules built in:
* GET requests only; nothing is ever posted, no login, no cookies kept.
* robots.txt is honoured by default (COLLECTOR_RESPECT_ROBOTS).
* A minimum delay is enforced between requests to the same host.
* An identifying User-Agent is sent.
Parsing is pure (HTML/JSON in, RawPosting out) so it is tested against saved fixtures.
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time
import urllib.robotparser
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlparse

import requests
from bs4 import BeautifulSoup

from .base import RawPosting, SearchQuery, SourceError, SourceRateLimited

log = logging.getLogger(__name__)


class PoliteFetcher:
    """Shared HTTP layer: robots.txt, per-host spacing, timeouts."""

    _host_lock = threading.Lock()
    _last_hit: dict[str, float] = {}
    _robots: dict[str, urllib.robotparser.RobotFileParser] = {}

    def __init__(self, user_agent: str, min_delay: float, respect_robots: bool = True,
                 timeout: float = 15, session: requests.Session | None = None):
        self.user_agent = user_agent
        self.min_delay = min_delay
        self.respect_robots = respect_robots
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept-Language": "en-IN,en;q=0.8"})

    def allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parts = urlparse(url)
        root = f"{parts.scheme}://{parts.netloc}"
        parser = self._robots.get(root)
        if parser is None:
            parser = urllib.robotparser.RobotFileParser()
            try:
                resp = self.session.get(f"{root}/robots.txt", timeout=self.timeout)
                parser.parse(resp.text.splitlines() if resp.status_code == 200 else [])
            except requests.RequestException:
                parser.parse(["User-agent: *", "Disallow: /"])  # unknown -> don't crawl
            self._robots[root] = parser
        return parser.can_fetch(self.user_agent, url)

    def _space(self, host: str) -> None:
        with self._host_lock:
            wait = self._last_hit.get(host, 0) + self.min_delay - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_hit[host] = time.monotonic()

    def get(self, url: str, headers: dict | None = None) -> requests.Response:
        if not self.allowed(url):
            raise SourceError(f"robots.txt disallows {urlparse(url).netloc}{urlparse(url).path}")
        self._space(urlparse(url).netloc)
        try:
            resp = self.session.get(url, headers=headers or {}, timeout=self.timeout)
        except requests.RequestException as exc:
            raise SourceError(f"Request failed: {exc}") from exc
        if resp.status_code == 429:
            retry = resp.headers.get("Retry-After", "")
            delay = int(retry) if retry.isdigit() else 900
            raise SourceRateLimited("Listing site rate limit hit.",
                                    datetime.now(UTC) + timedelta(seconds=delay))
        if resp.status_code >= 400:
            raise SourceError(f"HTTP {resp.status_code} from {urlparse(url).netloc}")
        return resp


def _text(node) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


# ---- LinkedIn public (guest) job search ------------------------------------

LINKEDIN_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"


def parse_linkedin_cards(html: str) -> list[RawPosting]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[RawPosting] = []
    for card in soup.select("div.base-card, li > div.base-search-card"):
        urn = card.get("data-entity-urn", "")
        link = card.select_one("a.base-card__full-link")
        title = _text(card.select_one(".base-search-card__title"))
        company = _text(card.select_one(".base-search-card__subtitle"))
        if not (title and company and link):
            continue
        url = link.get("href", "").split("?")[0]
        external_id = urn.rsplit(":", 1)[-1] if urn else hashlib.sha1(url.encode()).hexdigest()[:16]
        time_tag = card.select_one("time")
        posted_at = None
        if time_tag and time_tag.get("datetime"):
            try:
                posted_at = datetime.fromisoformat(time_tag["datetime"]).replace(tzinfo=UTC)
            except ValueError:
                posted_at = None
        out.append(RawPosting(
            platform="linkedin", external_id=external_id, url=url, title=title, company=company,
            location=_text(card.select_one(".job-search-card__location")), posted_at=posted_at,
        ))
    return out


class LinkedInListingSource:
    platform = "linkedin"

    def __init__(self, fetcher: PoliteFetcher, pages: int = 1):
        self.fetcher = fetcher
        self.pages = pages

    def search(self, query: SearchQuery) -> list[RawPosting]:
        results: dict[str, RawPosting] = {}
        locations = query.locations or ("India",)
        for role in query.roles:
            for loc in locations:
                for page in range(self.pages):
                    url = f"{LINKEDIN_SEARCH_URL}?{urlencode({'keywords': role, 'location': loc, 'start': page * 25})}"
                    for p in parse_linkedin_cards(self.fetcher.get(url).text):
                        results.setdefault(p.external_id, p)
                    if len(results) >= query.max_results:
                        return list(results.values())[: query.max_results]
        return list(results.values())


# ---- Naukri public search API ------------------------------------------------

NAUKRI_SEARCH_URL = "https://www.naukri.com/jobapi/v3/search"
NAUKRI_HEADERS = {"appid": "109", "systemid": "Naukri", "Accept": "application/json"}


def parse_naukri_json(payload: dict) -> list[RawPosting]:
    out: list[RawPosting] = []
    for job in payload.get("jobDetails") or []:
        job_id, title = str(job.get("jobId") or ""), (job.get("title") or "").strip()
        company = (job.get("companyName") or "").strip()
        if not (job_id and title and company):
            continue
        placeholders = {p.get("type"): p.get("label", "") for p in job.get("placeholders") or []}
        url = job.get("jdURL") or ""
        if url.startswith("/"):
            url = "https://www.naukri.com" + url
        created = job.get("createdDate")
        posted_at = datetime.fromtimestamp(created / 1000, tz=UTC) if isinstance(created, (int, float)) else None
        skills = [s.strip() for s in (job.get("tagsAndSkills") or "").split(",") if s.strip()]
        desc = BeautifulSoup(job.get("jobDescription") or "", "html.parser").get_text(" ", strip=True)
        exp = placeholders.get("experience", "")
        out.append(RawPosting(
            platform="naukri", external_id=job_id, url=url, title=title, company=company,
            location=placeholders.get("location", ""),
            description=f"{desc} Experience: {exp}".strip() if exp else desc,
            posted_at=posted_at, skills=skills,
        ))
    return out


class NaukriListingSource:
    platform = "naukri"

    def __init__(self, fetcher: PoliteFetcher):
        self.fetcher = fetcher

    def search(self, query: SearchQuery) -> list[RawPosting]:
        results: dict[str, RawPosting] = {}
        for role in query.roles:
            params = {"noOfResults": min(query.max_results, 20), "urlType": "search_by_keyword",
                      "searchType": "adv", "keyword": role, "pageNo": 1}
            if query.locations:
                params["location"] = ",".join(query.locations)
            resp = self.fetcher.get(f"{NAUKRI_SEARCH_URL}?{urlencode(params)}", headers=NAUKRI_HEADERS)
            try:
                payload = resp.json()
            except ValueError as exc:
                raise SourceError("Naukri returned a non-JSON response.") from exc
            for p in parse_naukri_json(payload):
                results.setdefault(p.external_id, p)
        return list(results.values())[: query.max_results]
