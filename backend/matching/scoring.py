"""REQ-6 relevance score: weighted keyword match, 0-100.

Weights (sum 100):
  skills      50  share of the user's skills found in the posting (title hits count double)
  role        30  best token overlap between a preferred role and the posting title
  location    10  posting location matches a preferred location, or is remote
  experience  10  user's years fall inside the posting's stated range
"""
from __future__ import annotations

import re
from dataclasses import dataclass

W_SKILLS, W_ROLE, W_LOCATION, W_EXPERIENCE = 50, 30, 10, 10

_STOP = {"and", "or", "the", "a", "an", "of", "for", "in", "to", "with", "-", "/", "&"}
_SENIORITY = {"sr", "senior", "jr", "junior", "intern", "lead", "trainee", "associate", "i", "ii", "iii"}
_EXP_RANGE = re.compile(r"(\d{1,2})\s*(?:-|to|–)\s*(\d{1,2})\s*(?:\+\s*)?(?:yrs?|years?)", re.I)
_EXP_MIN = re.compile(r"(\d{1,2})\s*\+?\s*(?:yrs?|years?)", re.I)
_REMOTE = re.compile(r"\b(remote|work from home|wfh|anywhere)\b", re.I)


@dataclass(frozen=True)
class ProfileView:
    skills: tuple[str, ...]
    roles: tuple[str, ...]
    locations: tuple[str, ...]
    years: int


# Common abbreviations in Indian job titles, expanded before comparing roles.
_ABBREV = {
    "ml": "machine learning", "ai": "artificial intelligence", "sde": "software development engineer",
    "swe": "software engineer", "dev": "developer", "engg": "engineer", "fe": "frontend",
    "be": "backend", "ds": "data scientist", "qa": "quality assurance",
}


def expand(text: str) -> str:
    return " ".join(_ABBREV.get(w, w) for w in re.split(r"[\s/,-]+", text.lower()) if w)


def tokens(text: str) -> set[str]:
    # keep tech tokens like c++, c#, node.js, .net
    return {t for t in re.findall(r"[a-z0-9][a-z0-9+#.]*[a-z0-9+#]|[a-z0-9]", text.lower()) if t not in _STOP}


def _contains(haystack: str, needle: str) -> bool:
    needle = needle.strip().lower()
    if not needle:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9+#])", haystack) is not None


def skill_score(p: ProfileView, title: str, body: str) -> float:
    skills = [s for s in p.skills if s.strip()]
    if not skills:
        return 0.0
    title_l, body_l = title.lower(), body.lower()
    points = 0.0
    for s in skills:
        if _contains(title_l, s):
            points += 1.0
        elif _contains(body_l, s):
            points += 0.5
    # Saturates once half the user's skills are matched with full weight.
    return min(1.0, points / max(1.0, len(skills) * 0.5))


def role_score(p: ProfileView, title: str) -> float:
    title_t = tokens(expand(title)) - _SENIORITY
    best = 0.0
    for role in p.roles:
        role_t = tokens(expand(role)) - _SENIORITY
        if role_t:
            best = max(best, len(role_t & title_t) / len(role_t))
    return best


def location_score(p: ProfileView, location: str, body: str) -> float:
    if _REMOTE.search(location) or _REMOTE.search(body[:500]):
        return 1.0
    if not p.locations:
        return 0.5  # no preference: neutral
    loc = location.lower()
    return 1.0 if any(_contains(loc, pl) for pl in p.locations) else 0.0


def experience_score(p: ProfileView, text: str) -> float:
    m = _EXP_RANGE.search(text)
    if m:
        lo, hi = sorted((int(m.group(1)), int(m.group(2))))
    else:
        m = _EXP_MIN.search(text)
        if not m:
            return 0.5  # unknown: neutral
        lo, hi = int(m.group(1)), 99
    if lo <= p.years <= hi:
        return 1.0
    gap = lo - p.years if p.years < lo else p.years - hi
    return max(0.0, 1.0 - 0.34 * gap)


def score(p: ProfileView, title: str, company: str, location: str, description: str,
          posting_skills: list[str] | None = None) -> int:
    body = f"{description} {' '.join(posting_skills or [])} {company}"
    total = (
        W_SKILLS * skill_score(p, title, body)
        + W_ROLE * role_score(p, title)
        + W_LOCATION * location_score(p, location, description)
        + W_EXPERIENCE * experience_score(p, f"{title} {description}")
    )
    return max(0, min(100, round(total)))
