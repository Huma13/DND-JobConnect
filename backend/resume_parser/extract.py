"""Issue #10 (REQ-2, REQ-4): read a resume and extract the Appendix B Profile fields.

pdfplumber / python-docx read the text; spaCy's PhraseMatcher finds the skills.
A blank English pipeline is used, so no model download is needed.

Nothing here touches the database or keeps the file (SRS 3.2).
"""

import io
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from functools import lru_cache

import pdfplumber
import spacy
from docx import Document
from spacy.matcher import PhraseMatcher
from spacy.util import filter_spans

from .skills_vocab import AMBIGUOUS, SKILLS

MIN_TEXT_CHARS = 50
MAX_TEXT_CHARS = 200_000
MAX_ROLES = 5
# Appendix B field lengths
MAX_NAME_CHARS = 100
MAX_SKILLS_CHARS = 500
MAX_QUALIFICATION_CHARS = 150
MAX_ROLES_CHARS = 300

SCANNED_MESSAGE = (
    "This looks like a scanned or image-only resume, so no text could be read from it. "
    "Please upload a text-based PDF or DOCX file."
)


class ResumeParseError(Exception):
    """The file could not be turned into usable text."""

    code = "unreadable_file"


class ScannedResumeError(ResumeParseError):
    """REQ-4: the file has (almost) no text, e.g. a scanned image-only PDF."""

    code = "scanned_resume"


@dataclass
class ParsedResume:
    full_name: str = ""
    skills: list[str] = field(default_factory=list)
    years_of_experience: int = 0
    highest_qualification: str = ""
    preferred_roles: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- text


def text_from_pdf(data: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)
    except Exception as exc:
        raise ResumeParseError(
            "This PDF could not be read. It may be damaged or protected."
        ) from exc


def text_from_docx(data: bytes) -> str:
    try:
        document = Document(io.BytesIO(data))
        lines: list[str] = []
        for block in document.iter_inner_content():  # paragraphs and tables, in order
            if hasattr(block, "rows"):
                for row in block.rows:
                    cells = []
                    for cell in row.cells:
                        text = cell.text.strip()
                        if text and text not in cells:  # merged cells repeat
                            cells.append(text)
                    lines.append(" | ".join(cells))
            else:
                lines.append(block.text)
        return "\n".join(lines)
    except Exception as exc:
        raise ResumeParseError("This DOCX could not be read. It may be damaged.") from exc


def extract_text(data: bytes, extension: str) -> str:
    """Return the resume text, or raise ScannedResumeError when there is none (REQ-4)."""
    text = text_from_pdf(data) if extension == ".pdf" else text_from_docx(data)
    if len(re.sub(r"\s+", "", text)) < MIN_TEXT_CHARS:
        raise ScannedResumeError(SCANNED_MESSAGE)
    return text[:MAX_TEXT_CHARS]


# ----------------------------------------------------------------------- sections

_SECTION_NAMES = {
    "skills": (
        "skills",
        "technical skills",
        "key skills",
        "core skills",
        "core competencies",
        "skills summary",
        "technologies",
        "tech stack",
        "technical proficiencies",
        "areas of expertise",
        "technical expertise",
    ),
    "experience": (
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "employment history",
        "work history",
        "internships",
        "internship experience",
        "professional background",
        "career history",
    ),
    "education": (
        "education",
        "academic background",
        "academics",
        "education and qualifications",
        "qualifications",
        "academic qualifications",
        "educational qualifications",
        "education and training",
    ),
    "summary": (
        "summary",
        "professional summary",
        "objective",
        "career objective",
        "profile",
        "about me",
        "about",
        "career summary",
        "personal statement",
    ),
    "other": (
        "projects",
        "academic projects",
        "personal projects",
        "certifications",
        "certificates",
        "achievements",
        "awards",
        "publications",
        "interests",
        "hobbies",
        "references",
        "extracurricular activities",
        "volunteering",
        "courses",
        "training",
        "personal details",
        "declaration",
    ),
}
_HEADING_LOOKUP = {name: section for section, names in _SECTION_NAMES.items() for name in names}
_INLINE_HEADING = re.compile(r"^([A-Za-z &/]{3,40}?)\s*[:\-–]\s*(\S.*)$")


def _normalise_heading(text: str) -> str:
    text = text.lower().replace("&", " and ")
    return " ".join(re.sub(r"[^a-z ]", " ", text).split())


def _heading_of(line: str) -> tuple[str | None, str]:
    """Return (section, rest-of-line) if the line starts a section."""
    if len(line) <= 40:
        section = _HEADING_LOOKUP.get(_normalise_heading(line))
        if section:
            return section, ""
    inline = _INLINE_HEADING.match(line)
    if inline:
        section = _HEADING_LOOKUP.get(_normalise_heading(inline.group(1)))
        if section:
            return section, inline.group(2).strip()
    return None, ""


def split_sections(text: str) -> tuple[list[str], dict[str, list[str]]]:
    """Split into the lines before the first heading and a dict of section -> lines."""
    header: list[str] = []
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        section, rest = _heading_of(line)
        if section:
            current = section
            sections.setdefault(section, [])
            if rest:
                sections[section].append(rest)
        elif current is None:
            header.append(line)
        else:
            sections[current].append(line)
    return header, sections


# ----------------------------------------------------------------------- helpers

_MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1
    )
}
_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_DATE = rf"(?:{_MONTH}\.?,?\s+(?:19|20)\d{{2}}|\d{{1,2}}/(?:19|20)\d{{2}}|(?:19|20)\d{{2}})"
_NOW = r"(?:present|current|currently|ongoing|now|till\s+date|to\s+date)"
_RANGE = re.compile(rf"(?P<start>{_DATE})\s*(?:-|–|—|to)\s*(?P<end>{_DATE}|{_NOW})", re.IGNORECASE)
_EXPLICIT_YEARS = re.compile(
    r"(\d{1,2})(?:\.\d)?\s*\+?\s*(?:years?|yrs?)\b[^.\n]{0,40}?experience"
    r"|experience\s+(?:of|:)\s*(\d{1,2})(?:\.\d)?\s*\+?\s*(?:years?|yrs?)",
    re.IGNORECASE,
)


def _clean_line(line: str) -> str:
    line = _RANGE.sub(" ", line)
    line = re.sub(r"\s+", " ", line)
    return line.strip(" |–—-,:;•*·\t")


def _fit_length(items: list[str], limit: int) -> list[str]:
    """Keep items, in order, while their joined length stays within the Appendix B limit."""
    kept: list[str] = []
    used = 0
    for item in items:
        used += len(item) + (2 if kept else 0)
        if used > limit:
            break
        kept.append(item)
    return kept


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


# -------------------------------------------------------------------------- name

_NAME_SHAPE = re.compile(r"^[A-Za-z][A-Za-z.'\-]*(?:\s+[A-Za-z][A-Za-z.'\-]*){1,3}$")
_NOT_A_NAME = re.compile(
    r"resume|curriculum|vitae|engineer|developer|analyst|student|scientist|designer|manager|"
    r"intern|fresher|email|phone|address|linkedin|github|objective|summary|profile|skills",
    re.IGNORECASE,
)


def extract_name(header: list[str]) -> str:
    for line in header[:6]:
        if _NAME_SHAPE.match(line) and not _NOT_A_NAME.search(line):
            name = line.title() if line.isupper() else line
            return name[:MAX_NAME_CHARS]
    return ""


# ------------------------------------------------------------------------ skills


def _key(tokens) -> str:
    return "".join(token.lower_ for token in tokens)


@lru_cache(maxsize=1)
def _skill_matchers():
    nlp = spacy.blank("en")
    general = PhraseMatcher(nlp.vocab, attr="LOWER")
    ambiguous = PhraseMatcher(nlp.vocab, attr="LOWER")
    lookup: dict[str, str] = {}
    for canonical, aliases in SKILLS.items():
        for term in (canonical, *aliases):
            doc = nlp.make_doc(term)
            lookup[_key(doc)] = canonical
            (ambiguous if term.lower() in AMBIGUOUS else general).add("SKILL", [doc])
    return nlp, general, ambiguous, lookup


def extract_skills(text: str, skills_section: str = "") -> list[str]:
    """Skills found anywhere in the resume. Ambiguous words (C, R, Go...) only count in Skills."""
    nlp, general, ambiguous, lookup = _skill_matchers()
    found: list[str] = []

    doc = nlp.make_doc(text)
    spans = filter_spans([doc[start:end] for _, start, end in general(doc)])
    found.extend(lookup[_key(span)] for span in spans)

    if skills_section:
        section_doc = nlp.make_doc(skills_section)
        spans = filter_spans([section_doc[s:e] for _, s, e in ambiguous(section_doc)])
        found.extend(lookup[_key(span)] for span in spans)

    return _fit_length(_dedupe(found), MAX_SKILLS_CHARS)


# ---------------------------------------------------------------------- experience


def _parse_month_index(text: str, today: date) -> int:
    """Return year*12+month for a date string, or for 'present'."""
    if re.fullmatch(_NOW, text.strip(), re.IGNORECASE):
        return today.year * 12 + today.month
    year = int(re.search(r"(?:19|20)\d{2}", text).group())
    name = re.search(_MONTH, text, re.IGNORECASE)
    numeric = re.match(r"(\d{1,2})/", text.strip())
    month = 1
    if name:
        month = _MONTHS[name.group()[:3].lower()]
    elif numeric:
        month = min(max(int(numeric.group(1)), 1), 12)
    return year * 12 + month


def extract_years(experience_lines: list[str], today: date) -> int:
    """Total years: merged date ranges in the Experience section, or an explicit statement."""
    intervals = []
    for match in _RANGE.finditer("\n".join(experience_lines)):
        start = _parse_month_index(match.group("start"), today)
        end = _parse_month_index(match.group("end"), today)
        if end > start:
            intervals.append((start, end))
    intervals.sort()

    total_months = 0
    current_start = current_end = None
    for start, end in intervals:
        if current_end is None or start > current_end:
            if current_end is not None:
                total_months += current_end - current_start
            current_start, current_end = start, end
        else:
            current_end = max(current_end, end)
    if current_end is not None:
        total_months += current_end - current_start

    return int(total_months / 12 + 0.5)


def extract_stated_years(text: str) -> int:
    """'5+ years of experience' style statements anywhere in the resume."""
    stated = [int(a or b) for a, b in _EXPLICIT_YEARS.findall(text)]
    return max(stated, default=0)


# ----------------------------------------------------------------- qualification

_STRONG_DEGREES = (
    (5, r"\b(?:ph\.?\s?d\.?|doctorate|doctor of philosophy)(?=\W|$)"),
    (
        4,
        r"\b(?:m\.?\s?tech|m\.?\s?sc|mca|mba|master(?:'?s)?\s+(?:of|in)|masters|post\s?graduate)"
        r"(?=\W|$)",
    ),
    (
        3,
        r"\b(?:b\.?\s?tech|b\.?\s?sc|bca|bba|b\.?\s?com|bachelor(?:'?s)?\s+(?:of|in)|bachelors)"
        r"(?=\W|$)",
    ),
    (2, r"\bdiploma\b"),
    (1, r"\b(?:higher secondary|senior secondary|hsc|puc|pre-?university|12th|class xii)\b"),
    (0, r"\b(?:secondary school|sslc|10th|matriculation)\b"),
)
# Short abbreviations are only trusted inside an Education section, and only in capitals.
_WEAK_DEGREES = (
    (4, r"\b(?:M\.?E\.?|M\.?S\.?|M\.?A\.?)(?=\s|,|$)"),
    (3, r"\b(?:B\.?E\.?|B\.?S\.?|B\.?A\.?)(?=\s|,|$)"),
)
_STRONG = [(level, re.compile(pattern, re.IGNORECASE)) for level, pattern in _STRONG_DEGREES]
_WEAK = [(level, re.compile(pattern)) for level, pattern in _WEAK_DEGREES]
_INSTITUTION = re.compile(
    r"\b(?:university|institute|college|school|academy|iit|nit)\b", re.IGNORECASE
)


def _degree_level(line: str, allow_weak: bool) -> int:
    levels = [level for level, pattern in _STRONG if pattern.search(line)]
    if allow_weak:
        levels += [level for level, pattern in _WEAK if pattern.search(line)]
    return max(levels, default=-1)


def extract_qualification(education_lines: list[str], all_lines: list[str]) -> str:
    """The highest degree found, e.g. 'B.Tech CSE, PES University'."""
    lines = education_lines or all_lines
    allow_weak = bool(education_lines)

    best_index, best_level = -1, -1
    for index, line in enumerate(lines):
        level = _degree_level(line, allow_weak)
        if level > best_level:
            best_index, best_level = index, level
    if best_index < 0:
        return ""

    text = _clean_line(lines[best_index])
    if not _INSTITUTION.search(text):
        for neighbour in (best_index + 1, best_index - 1):
            if not 0 <= neighbour < len(lines):
                continue
            line = lines[neighbour]
            if _INSTITUTION.search(line) and _degree_level(line, allow_weak) < 0:
                text = f"{text}, {_clean_line(line)}"
                break
    return text[:MAX_QUALIFICATION_CHARS].strip(" ,")


# ------------------------------------------------------------------------- roles

_TITLE_WORDS = (
    r"engineer|developer|analyst|scientist|intern|manager|consultant|designer|architect|"
    r"administrator|lead|specialist|tester|programmer|associate|researcher|trainee|executive|"
    r"officer|director|coordinator|technician|assistant"
)
_HAS_TITLE = re.compile(rf"\b(?:{_TITLE_WORDS})s?\b", re.IGNORECASE)
_TITLE_PHRASE = rf"[A-Za-z+#/\- ]{{2,40}}?\b(?:{_TITLE_WORDS})"
_OBJECTIVE_ROLE = (
    # "... as a Software Engineer", "the position of Data Analyst"
    re.compile(
        rf"\b(?:as|position of|role of)\s+(?:an?\s+|the\s+)?({_TITLE_PHRASE})s?\b", re.IGNORECASE
    ),
    # "seeking a Software Engineer role"
    re.compile(
        rf"\bseeking\s+(?:an?\s+|the\s+)?({_TITLE_PHRASE})s?\s+(?:role|position|opportunit)",
        re.IGNORECASE,
    ),
)
_SEGMENT_SPLIT = re.compile(r"\s+(?:at|@)\s+|\s*[|,–—]\s*|\s+-\s+")
_BULLET = ("•", "-", "*", "·", "–", "▪", "●")
_ACTION_WORD = re.compile(r"^(?:led|built|ran|wrote|won|made|took|did)$", re.IGNORECASE)


def _looks_like_title(text: str) -> bool:
    words = text.split()
    if not 1 <= len(words) <= 6 or not _HAS_TITLE.search(text):
        return False
    first = words[0]
    if first.lower().endswith("ed") or _ACTION_WORD.match(first):
        return False  # "Developed REST APIs..." is a sentence, not a title
    return not re.search(r"[.@\d]", text)


def _title_from_line(line: str) -> str:
    if line.startswith(_BULLET):
        return ""
    for segment in _SEGMENT_SPLIT.split(_clean_line(line)):
        segment = segment.strip()
        if _looks_like_title(segment):
            return segment
    return ""


def extract_roles(header: list[str], summary: list[str], experience: list[str]) -> list[str]:
    """Up to five job titles: headline, objective, then titles held (REQ-2)."""
    roles: list[str] = []

    for line in header[1:8]:  # the line under the name is usually a headline
        if _looks_like_title(line):
            roles.append(line)
            break

    summary_text = " ".join(summary)
    for pattern in _OBJECTIVE_ROLE:
        for match in pattern.finditer(summary_text):
            candidate = match.group(1).strip()
            if _looks_like_title(candidate):
                roles.append(candidate)

    for line in experience:
        title = _title_from_line(line)
        if title:
            roles.append(title)

    roles = [" ".join(role.split()) for role in roles]
    return _fit_length(_dedupe(roles)[:MAX_ROLES], MAX_ROLES_CHARS)


# ---------------------------------------------------------------------- top level


def parse_resume_text(text: str, today: date | None = None) -> ParsedResume:
    today = today or date.today()
    header, sections = split_sections(text)
    all_lines = [line.strip() for line in text.splitlines() if line.strip()]

    experience = sections.get("experience", [])
    years = extract_years(experience, today)
    years = max(years, extract_stated_years(text))

    return ParsedResume(
        full_name=extract_name(header),
        skills=extract_skills(text, "\n".join(sections.get("skills", []))),
        years_of_experience=min(years, 99),
        highest_qualification=extract_qualification(sections.get("education", []), all_lines),
        preferred_roles=extract_roles(header, sections.get("summary", []), experience),
    )


def parse_resume_file(data: bytes, extension: str, today: date | None = None) -> ParsedResume:
    """Read a PDF or DOCX held in memory and return the extracted Profile fields."""
    return parse_resume_text(extract_text(data, extension), today)
