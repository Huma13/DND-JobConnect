"""Issue #12: tips to improve a profile for targeted roles.

Acceptance criteria:
  * Show keywords that are common in the target postings but missing
    from the user's resume.
  * Provide headline and summary suggestions.

Pure Python, no dependencies. Call `generate_profile_tips(...)` from any
web framework and return `.to_dict()` as JSON.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

STOPWORDS = set("""
a an the and or but if of to in on at by for with from as is are was were be been being it its this that these those
you your we our they their he she i us them not no so than then too very can could should would will may might must
about into over under out up down off across within without between per via etc also such other any all each more most
some both either who whom which what when where why how
""".split())

# Words that show up in nearly every posting and say nothing about skills.
GENERIC = set("""
experience experienced team teams work working works years year strong ability able skills skill role roles company
companies job jobs candidate candidates join looking required preferred requirements requirement responsibilities
responsibility including include related knowledge understanding new good excellent plus build building use using used
please apply opportunity opportunities benefits position degree bachelor bachelors master masters environment
environments etc looking seeking ideal proven demonstrated excellent communication collaborate collaboration help
ensure support provide day passion fast growing equal employer world high quality based
""".split())

_TOKEN_RE = re.compile(r"[a-z][a-z0-9+#./-]*")


def _tokenize(text: str) -> list[str]:
    tokens = []
    for tok in _TOKEN_RE.findall(text.lower()):
        tok = tok.strip("./-")
        if tok:
            tokens.append(tok)
    return tokens


def _is_keyword_token(tok: str) -> bool:
    return tok not in STOPWORDS and tok not in GENERIC and len(tok) > 1


_SEGMENT_RE = re.compile(r"[,;:!?()\[\]\n|\u2022]|\.(?:\s|$)")
TITLE_WORDS = {"engineer", "developer", "manager", "analyst", "specialist", "lead", "senior", "junior", "intern"}


def _candidate_phrases(text: str, exclude: frozenset[str] = frozenset()) -> set[str]:
    """Unigrams and bigrams (adjacent, both meaningful) found in one text.

    Bigrams never span a comma, period or bullet, so "microservices, REST"
    does not produce a false phrase.
    """
    def is_ok(token: str) -> bool:
        return _is_keyword_token(token) and token not in exclude

    phrases: set[str] = set()
    for segment in _SEGMENT_RE.split(text):
        tokens = _tokenize(segment)
        phrases.update(t for t in tokens if is_ok(t))
        for i in range(len(tokens) - 1):
            a, b = tokens[i], tokens[i + 1]
            if is_ok(a) and is_ok(b):
                phrases.add(f"{a} {b}")
    return phrases


@dataclass
class Keyword:
    keyword: str
    share: float  # fraction of target postings that mention it (0-1)
    postings: int  # number of postings that mention it


@dataclass
class ProfileTips:
    target_role: str
    postings_analyzed: int
    missing_keywords: list[Keyword] = field(default_factory=list)
    matched_keywords: list[Keyword] = field(default_factory=list)
    coverage: float = 0.0  # share of top posting keywords already in resume
    headline_suggestions: list[str] = field(default_factory=list)
    summary_suggestions: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _top_keywords(postings: list[str], min_share: float, limit: int, exclude: frozenset[str]) -> list[Keyword]:
    n = len(postings)
    doc_freq: dict[str, int] = {}
    for p in postings:
        for ph in _candidate_phrases(p, exclude):
            doc_freq[ph] = doc_freq.get(ph, 0) + 1

    min_count = max(2, round(min_share * n)) if n > 1 else 1
    kept = {k: c for k, c in doc_freq.items() if c >= min_count}

    # Drop a single word when a kept phrase containing it is just as common
    # (e.g. keep "machine learning", drop "machine" with the same count).
    for phrase, count in list(kept.items()):
        if " " in phrase:
            for tok in phrase.split():
                if tok in kept and kept[tok] <= count:
                    del kept[tok]

    ranked = sorted(kept.items(), key=lambda kv: (-kv[1], -len(kv[0].split()), kv[0]))
    return [Keyword(k, round(c / n, 2), c) for k, c in ranked[:limit]]


def generate_profile_tips(
    resume_text: str,
    target_postings: list[str],
    target_role: str,
    current_headline: str = "",
    current_summary: str = "",
    min_share: float = 0.3,
    limit: int = 25,
) -> ProfileTips:
    """Compare a resume against target job postings and suggest improvements."""
    postings = [p for p in target_postings if p and p.strip()]
    tips = ProfileTips(target_role=target_role.strip(), postings_analyzed=len(postings))

    if not postings:
        tips.notes.append("Add at least one target job posting to get keyword tips.")
        return tips
    if len(postings) < 3:
        tips.notes.append(
            f"Only {len(postings)} posting(s) analyzed; tips get more reliable with 5 or more."
        )
    if not resume_text.strip():
        tips.notes.append("No resume text found. Upload a resume first (see #9 and #13).")

    # The target role's own words ("backend engineer") are not skills to add.
    exclude = frozenset(_tokenize(target_role)) | TITLE_WORDS
    top = _top_keywords(postings, min_share, limit, exclude)
    resume_norm = " " + " ".join(_tokenize(resume_text)) + " "

    for kw in top:
        (tips.matched_keywords if f" {kw.keyword} " in resume_norm else tips.missing_keywords).append(kw)

    tips.coverage = round(len(tips.matched_keywords) / len(top), 2) if top else 0.0

    role = tips.target_role.title()
    have = [k.keyword for k in tips.matched_keywords[:3]]
    lack = [k.keyword for k in tips.missing_keywords[:3]]

    # Headline suggestions use only keywords the resume already supports,
    # so we never encourage claiming skills the user does not have.
    if have:
        tips.headline_suggestions.append(f"{role} | " + " · ".join(have))
        tips.headline_suggestions.append(f"{role} specializing in {_join(have[:2])}")
    else:
        tips.headline_suggestions.append(f"{role} | add your strongest skill here")
    if current_headline and role.lower() not in current_headline.lower():
        tips.notes.append(f'Your headline does not mention the target role "{role}".')

    summary = (
        f"{role} with [X years] of experience in {_join(have) if have else '[your core skills]'}. "
        f"Delivered [a measurable result, e.g. reduced X by Y%]. "
        f"Looking to apply this experience to [target company or domain]."
    )
    tips.summary_suggestions.append(summary)
    if lack:
        tips.summary_suggestions.append(
            f"If it is true for you, work in: {_join(lack)}. Back each with one concrete example."
        )
    if current_summary:
        missing_in_summary = [k.keyword for k in top[:8] if k.keyword not in current_summary.lower()]
        if missing_in_summary:
            tips.notes.append("Top keywords absent from your summary: " + ", ".join(missing_in_summary[:5]) + ".")

    if tips.missing_keywords:
        tips.notes.append("Only add missing keywords you can honestly back up with experience.")
    return tips


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


if __name__ == "__main__":
    import json

    demo = generate_profile_tips(
        resume_text="Python developer. Built REST APIs with Flask and PostgreSQL. Used Docker and Git.",
        target_postings=[
            "Backend engineer: Python, Django, REST APIs, PostgreSQL, Docker, Kubernetes, CI/CD, AWS.",
            "Looking for a Python engineer with AWS, Kubernetes, microservices, REST APIs and PostgreSQL.",
            "Backend developer. Python, FastAPI, Docker, AWS, CI/CD pipelines, microservices, REST APIs.",
        ],
        target_role="backend engineer",
        current_headline="Python developer",
    )
    print(json.dumps(demo.to_dict(), indent=2))
