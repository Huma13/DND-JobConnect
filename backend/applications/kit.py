"""Apply kit builder (issue #20): a tailored resume, cover letter and standard answers.

Built only from the user's profile and the posting, so nothing is invented.
"""
from __future__ import annotations

import re

from matching.models import JobPosting
from resume_parser.models import Profile

EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")


def matched_skills(profile: Profile, posting: JobPosting) -> list[str]:
    text = f"{posting.title} {posting.description} {' '.join(posting.skills)}".lower()
    return [s for s in profile.skills if re.search(rf"(?<!\w){re.escape(s.lower())}(?!\w)", text)]


def build_kit(profile: Profile | None, user, posting: JobPosting) -> dict:
    name = profile.full_name if profile and profile.full_name else (user.get_full_name() or user.email)
    skills = list(profile.skills) if profile else []
    years = profile.years_of_experience if profile else 0
    roles = list(profile.preferred_roles) if profile else []
    relevant = matched_skills(profile, posting) if profile else []
    others = [s for s in skills if s not in relevant]

    lines = [name, user.email, "", f"Application for: {posting.title}, {posting.company}", ""]
    if profile and profile.highest_qualification:
        lines += ["EDUCATION", profile.highest_qualification, ""]
    summary = f"{years} year(s) of experience"
    summary += f" targeting roles such as {', '.join(roles[:2])}." if roles else "."
    lines += ["SUMMARY", summary, ""]
    if relevant:
        lines += ["SKILLS RELEVANT TO THIS ROLE", ", ".join(relevant), ""]
    if others:
        lines += ["OTHER SKILLS", ", ".join(others), ""]
    resume = "\n".join(lines).strip() + "\n"

    top = ", ".join(relevant[:3] or skills[:3])
    experience = f" I bring {years} year(s) of experience" + (f" with {top}." if top else ".") if years or top else ""
    cover = (f"Dear Hiring Team at {posting.company},\n\n"
             f"I am writing to apply for the {posting.title} position.{experience}\n\n"
             f"I would welcome the chance to discuss how I can contribute to {posting.company}.\n\n"
             f"Kind regards,\n{name}\n")
    answers = {
        "Why are you interested in this role?":
            f"The {posting.title} role at {posting.company} matches my background" + (f" in {top}." if top else "."),
        "Years of relevant experience": str(years),
        "Key skills": ", ".join(relevant or skills),
        "Preferred locations": ", ".join(profile.preferred_locations) if profile else "",
        "Highest qualification": profile.highest_qualification if profile else "",
    }
    return {"resume_text": resume, "cover_letter": cover, "answers": answers}


def find_contact_email(posting: JobPosting) -> str:
    m = EMAIL.search(posting.description or "")
    return m.group(0) if m else ""
