"""REQ-7: the same role at the same company is one posting, whatever the platform."""
import hashlib
import re

_COMPANY_SUFFIX = re.compile(
    r"\b(private|pvt|limited|ltd|llp|inc|incorporated|corp|corporation|co|company|"
    r"technologies|technology|tech|solutions|india|global|services|software)\b\.?",
    re.I,
)
_TITLE_NOISE = re.compile(r"\(.*?\)|\[.*?\]|\b(urgent|hiring|immediate joiner[s]?|wfh|remote)\b", re.I)
_TITLE_ALIASES = {"sr": "senior", "jr": "junior", "engg": "engineer", "dev": "developer", "swe": "software engineer"}


def _clean(text: str) -> str:
    text = re.sub(r"[^a-z0-9+# ]", " ", text.lower())
    return " ".join(text.split())


def normalize_company(company: str) -> str:
    cleaned = _clean(_COMPANY_SUFFIX.sub(" ", company))
    return cleaned or _clean(company)


def normalize_title(title: str) -> str:
    words = _clean(_TITLE_NOISE.sub(" ", title)).split()
    return " ".join(_TITLE_ALIASES.get(w, w) for w in words)


def dedup_key(title: str, company: str) -> str:
    return hashlib.sha256(f"{normalize_title(title)}|{normalize_company(company)}".encode()).hexdigest()
