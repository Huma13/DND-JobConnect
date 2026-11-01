"""Recruiter Outreach (SAD): suggestions, drafts, daily limits and duplicate blocking (REQ-14..17)."""
from __future__ import annotations

import hashlib
import re
from datetime import timedelta
from urllib.parse import urlparse

from django.db import transaction
from django.utils import timezone

from applications.kit import matched_skills
from applications.services import Blocked
from integrations.base import SubmitError, SubmitRateLimited
from integrations.x_dm import get_x_messenger
from matching.models import JobPosting
from resume_parser.models import Profile

from .models import (
    DEFAULT_OUTREACH_LIMIT,
    LINKEDIN_NOTE_MAX,
    OutreachMessage,
    OutreachSetting,
    Recruiter,
)

_LINKEDIN = re.compile(r"https?://(?:[\w\-]+\.)?linkedin\.com/in/[\w\-%]+/?", re.I)
_HANDLE = re.compile(r"(?<![\w@])@(\w{1,15})\b")
_X_STATUS = re.compile(r"^/(\w{1,15})/status/")
_RESERVED = {"i", "home", "search", "hashtag", "intent", "share"}


# ---- suggestions (REQ-14) ---------------------------------------------------------

def suggest_recruiters(posting: JobPosting) -> list[Recruiter]:
    """Create the recruiter rows we can find from the posting itself, then return all of them."""
    found: list[dict] = []
    parsed = urlparse(posting.url)
    m = _X_STATUS.match(parsed.path) if parsed.netloc.lower().endswith(("x.com", "twitter.com")) else None
    if m and m.group(1).lower() not in _RESERVED:
        found.append(dict(name=f"@{m.group(1)}", x_handle=m.group(1),
                          reason="Posted this role on X, so they are the hiring contact."))
    for url in dict.fromkeys(_LINKEDIN.findall(posting.description or "")):
        slug = url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
        found.append(dict(name=slug, linkedin_url=url.rstrip("/"),
                          reason=f"Their LinkedIn profile is listed in the {posting.company} posting."))
    for handle in dict.fromkeys(_HANDLE.findall(posting.description or "")):
        if not any(f.get("x_handle", "").lower() == handle.lower() for f in found):
            found.append(dict(name=f"@{handle}", x_handle=handle,
                              reason=f"Mentioned in the {posting.company} posting."))
    for f in found:
        key = {"x_handle": f["x_handle"]} if "x_handle" in f else {"linkedin_url": f["linkedin_url"]}
        Recruiter.objects.get_or_create(posting=posting, **key, defaults=f)
    return list(Recruiter.objects.filter(posting=posting))


# ---- drafts (REQ-15) --------------------------------------------------------------

def draft_message(user, recruiter: Recruiter, channel: str) -> str:
    posting = recruiter.posting
    profile = Profile.objects.filter(user=user).first()
    first = recruiter.name.lstrip("@").split()[0] if recruiter.name else "there"
    skills = (matched_skills(profile, posting) if profile else [])[:3] or (profile.skills[:3] if profile else [])
    years = profile.years_of_experience if profile else 0
    who = profile.full_name if profile and profile.full_name else user.email.split("@")[0]
    about = ""
    if skills:
        tail = f" with {years} year(s) of experience." if years else "."
        about = f" My background is in {', '.join(skills)}{tail}"
    if channel == "linkedin":
        return (f"Hi {first}, I saw the {posting.title} opening at {posting.company} and I'm keen to apply."
                f"{about} Happy to connect. - {who}")[:LINKEDIN_NOTE_MAX]
    return (f"Hi {first}, I came across the {posting.title} role at {posting.company}."
            f"{about} I'd love to chat if you are the right person. Thanks, {who}")


def channel_for(recruiter: Recruiter, requested: str | None) -> str:
    if requested in ("linkedin", "x"):
        if requested == "linkedin" and not recruiter.linkedin_url:
            raise Blocked("This recruiter has no LinkedIn profile.", 400)
        if requested == "x" and not recruiter.x_handle:
            raise Blocked("This recruiter has no X handle.", 400)
        return requested
    return "x" if recruiter.x_handle else "linkedin"


# ---- limits (REQ-16) --------------------------------------------------------------

def get_setting(user, platform: str) -> OutreachSetting:
    return OutreachSetting.objects.get_or_create(user=user, platform=platform)[0]


def sent_today(user, platform: str) -> int:
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return OutreachMessage.objects.filter(user=user, platform=platform, status=OutreachMessage.Status.SENT,
                                          sent_at__gte=start, sent_at__lt=start + timedelta(days=1)).count()


def check_limit(user, platform: str) -> None:
    limit = (OutreachSetting.objects.filter(user=user, platform=platform)
             .values_list("daily_limit", flat=True).first())
    limit = DEFAULT_OUTREACH_LIMIT if limit is None else limit
    if sent_today(user, platform) >= limit:
        raise Blocked(f"Daily outreach limit of {limit} on {platform} reached.", 429)


# ---- identical bulk messages (REQ-17) ---------------------------------------------

def text_hash(body: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", body).strip().lower().encode()).hexdigest()


def check_not_bulk(msg: OutreachMessage) -> None:
    """The same text may go to one recipient only; a second recipient is rejected."""
    clash = (OutreachMessage.objects.filter(user=msg.user, body_hash=text_hash(msg.body),
                                            status=OutreachMessage.Status.SENT)
             .exclude(recruiter=msg.recruiter).exists())
    if clash:
        raise Blocked("This exact message was already sent to someone else. Personalise it first.", 409)


# ---- sending ----------------------------------------------------------------------

def _guard(msg: OutreachMessage) -> None:
    if msg.user.automation_paused:
        raise Blocked("Automation is paused.", 409)
    if msg.status == OutreachMessage.Status.SENT:
        raise Blocked("This message was already sent.", 409)
    if not msg.body.strip():
        raise Blocked("The message is empty.", 400)
    if msg.platform == "linkedin" and len(msg.body) > LINKEDIN_NOTE_MAX:
        raise Blocked(f"LinkedIn notes are limited to {LINKEDIN_NOTE_MAX} characters.", 400)
    check_not_bulk(msg)
    check_limit(msg.user, msg.platform)


def _finish(msg: OutreachMessage, detail: str = "") -> OutreachMessage:
    msg.status, msg.sent_at, msg.body_hash, msg.detail = (OutreachMessage.Status.SENT, timezone.now(),
                                                         text_hash(msg.body), detail)
    msg.save()
    return msg


def send_via_api(msg: OutreachMessage) -> OutreachMessage:
    """X messages go through the API."""
    if msg.platform != "x":
        raise Blocked("LinkedIn notes are sent by you: open the profile, send it, then mark it as sent.", 400)
    with transaction.atomic():
        type(msg.user).objects.select_for_update().get(pk=msg.user.pk)
        _guard(msg)
        try:
            event_id = get_x_messenger().send(msg.recruiter.x_handle, msg.body)
        except SubmitRateLimited as exc:
            raise Blocked(str(exc), 429) from exc
        except SubmitError as exc:
            msg.status, msg.detail = OutreachMessage.Status.FAILED, str(exc)[:300]
            msg.save()
            return msg
        return _finish(msg, f"dm_event_id={event_id}")


def mark_sent(msg: OutreachMessage) -> OutreachMessage:
    """LinkedIn: the user sent the note themselves from the profile the app opened."""
    if msg.platform != "linkedin":
        raise Blocked("X messages are sent by the app; use send.", 400)
    with transaction.atomic():
        type(msg.user).objects.select_for_update().get(pk=msg.user.pk)
        _guard(msg)
        return _finish(msg, "Sent manually by the user.")
