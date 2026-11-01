"""ATS adapters for company career pages (issue #22): Greenhouse and Lever.

An adapter takes the posting URL, the applicant and the apply kit, submits the application and
returns a small result dict. A CAPTCHA response raises CaptchaDetected so the caller can pause.
"""
from __future__ import annotations

import re
from typing import Protocol
from urllib.parse import urlparse

import requests
from django.conf import settings

from .base import CaptchaDetected, SubmitError

TIMEOUT = 20
_CAPTCHA = re.compile(r"captcha|are you a robot|verify you are human", re.I)

_GREENHOUSE = re.compile(r"^/(?:embed/job_app\?for=)?(?P<board>[\w\-]+)/jobs/(?P<job>\d+)")
_LEVER = re.compile(r"^/(?P<company>[\w\-]+)/(?P<job>[0-9a-f\-]{36})")


class IAtsAdapter(Protocol):
    name: str

    def submit(self, url: str, applicant: dict, kit: dict) -> dict: ...


def detect_ats(url: str) -> str | None:
    host = urlparse(url).netloc.lower()
    if host.endswith("greenhouse.io"):
        return "greenhouse"
    if host.endswith("lever.co"):
        return "lever"
    return None


def _check(resp: requests.Response) -> None:
    if resp.status_code < 400:
        return
    if _CAPTCHA.search(resp.text):
        raise CaptchaDetected("The career page asked for a CAPTCHA.")
    raise SubmitError(f"The career page rejected the application (HTTP {resp.status_code}).")


class GreenhouseAdapter:
    name = "greenhouse"

    def submit(self, url: str, applicant: dict, kit: dict) -> dict:
        m = _GREENHOUSE.match(urlparse(url).path)
        if not m:
            raise SubmitError("Not a Greenhouse job URL.")
        if not settings.GREENHOUSE_API_KEY:
            raise SubmitError("GREENHOUSE_API_KEY is not configured.")
        first, _, last = applicant["name"].partition(" ")
        api = f"https://boards-api.greenhouse.io/v1/boards/{m['board']}/jobs/{m['job']}"
        try:
            resp = requests.post(api, auth=(settings.GREENHOUSE_API_KEY, ""), timeout=TIMEOUT, data={
                "first_name": first, "last_name": last or first, "email": applicant["email"],
                "cover_letter_text": kit["cover_letter"], "resume_text": kit["resume_text"]})
        except requests.RequestException as exc:
            raise SubmitError(f"Could not reach Greenhouse: {type(exc).__name__}") from exc
        _check(resp)
        return {"ats": "greenhouse", "http_status": resp.status_code}


class LeverAdapter:
    name = "lever"

    def submit(self, url: str, applicant: dict, kit: dict) -> dict:
        m = _LEVER.match(urlparse(url).path)
        if not m:
            raise SubmitError("Not a Lever job URL.")
        if not settings.LEVER_API_KEY:
            raise SubmitError("LEVER_API_KEY is not configured.")
        api = f"https://api.lever.co/v0/postings/{m['company']}/{m['job']}"
        try:
            resp = requests.post(
                api, params={"key": settings.LEVER_API_KEY}, timeout=TIMEOUT,
                data={"name": applicant["name"], "email": applicant["email"], "comments": kit["cover_letter"]},
                files={"resume": ("resume.txt", kit["resume_text"].encode(), "text/plain")})
        except requests.RequestException as exc:
            raise SubmitError(f"Could not reach Lever: {type(exc).__name__}") from exc
        _check(resp)
        return {"ats": "lever", "http_status": resp.status_code}


_ADAPTERS = {"greenhouse": GreenhouseAdapter, "lever": LeverAdapter}


def get_ats_adapter(name: str) -> IAtsAdapter:
    try:
        return _ADAPTERS[name]()
    except KeyError as exc:
        raise SubmitError(f"No adapter for {name}.") from exc
