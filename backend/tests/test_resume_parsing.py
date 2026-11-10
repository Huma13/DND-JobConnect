"""Issues #9 and #10: resume upload validation and Appendix B field extraction."""

import io
from datetime import date
from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from docx import Document
from rest_framework.test import APIClient

from accounts.models import User
from resume_parser import extract, upload
from resume_parser.models import Profile

URL = "/api/resume/upload/"
PROFILE_URL = "/api/resume/profile/"
TODAY = date(2024, 7, 1)

SAMPLE_LINES = [
    "Huma Khan",
    "Backend Developer",
    "huma@example.com | +91 98765 43210 | Bengaluru",
    "",
    "SUMMARY",
    "Backend developer seeking a role as Software Engineer in a product team.",
    "",
    "SKILLS",
    "Python, Django, REST APIs, PostgreSQL, Docker, Git, C++, SQL, Go",
    "",
    "EXPERIENCE",
    "Software Engineer Intern, Acme Corp        Jan 2022 - Jun 2022",
    "- Built REST APIs using Django and PostgreSQL",
    "Backend Developer | Globex                  Jul 2022 - Present",
    "- Developed microservices with Docker and Kubernetes",
    "",
    "EDUCATION",
    "B.Tech CSE, PES University                   2018 - 2022",
    "Higher Secondary, ABC School                 2016 - 2018",
    "",
    "PROJECTS",
    "Job portal using React and Node.js",
]
SAMPLE_TEXT = "\n".join(SAMPLE_LINES)


# ------------------------------------------------------------------ file builders


def make_docx(lines, table_rows=None) -> bytes:
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    if table_rows:
        table = document.add_table(rows=len(table_rows), cols=len(table_rows[0]))
        for r, row in enumerate(table_rows):
            for c, value in enumerate(row):
                table.cell(r, c).text = value
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_pdf(lines) -> bytes:
    """A tiny text PDF (ASCII only). An empty list gives a page with no text, like a scan."""

    def esc(text):
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    stream = "BT /F1 11 Tf 50 780 Td 14 TL\n" + "".join(f"({esc(t)}) Tj T*\n" for t in lines) + "ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return out


# ------------------------------------------------------------------ extraction (#10)


def test_sample_resume_fields():
    parsed = extract.parse_resume_text(SAMPLE_TEXT, today=TODAY)
    assert parsed.full_name == "Huma Khan"
    for skill in (
        "Python",
        "Django",
        "REST APIs",
        "PostgreSQL",
        "Docker",
        "Git",
        "C++",
        "SQL",
        "Go",
    ):
        assert skill in parsed.skills
    assert "Kubernetes" in parsed.skills  # found outside the Skills section too
    assert parsed.years_of_experience == 2  # 5 + 24 months
    assert parsed.highest_qualification == "B.Tech CSE, PES University"
    assert parsed.preferred_roles[0] == "Backend Developer"
    assert "Software Engineer" in parsed.preferred_roles
    assert "Software Engineer Intern" in parsed.preferred_roles
    assert len(parsed.preferred_roles) <= 5


def test_ambiguous_skills_only_count_in_skills_section():
    assert "Go" not in extract.parse_resume_text("I like to go home and read.\n" * 5, TODAY).skills
    with_section = "Jane Doe\nSKILLS\nGo, R, Python\n" + "x" * 60
    skills = extract.parse_resume_text(with_section, TODAY).skills
    assert {"Go", "R", "Python"} <= set(skills)


def test_inline_skills_heading():
    parsed = extract.parse_resume_text(
        "Jane Doe\nSkills: Java, Spring Boot, MySQL\n" + "y" * 60, TODAY
    )
    assert {"Java", "Spring Boot", "MySQL"} <= set(parsed.skills)


def test_language_lines_inside_skills_are_not_a_new_section():
    text = "Jane Doe\nTechnical Skills\nLanguages: Python, R, SQL\nTools: Git, Docker\n" + "k" * 60
    skills = extract.parse_resume_text(text, TODAY).skills
    assert {"Python", "R", "SQL", "Git", "Docker"} <= set(skills)


def test_aliases_map_to_canonical_names():
    parsed = extract.parse_resume_text(
        "Jane Doe\nTech: nodejs, k8s, postgres, sklearn\n" + "z" * 60, TODAY
    )
    assert {"Node.js", "Kubernetes", "PostgreSQL", "scikit-learn"} <= set(parsed.skills)


def test_fresher_education_dates_do_not_count_as_experience():
    text = "Ravi Kumar\nEDUCATION\nB.E. Computer Science, VTU 2020 - 2024\n" + "q" * 60
    assert extract.parse_resume_text(text, TODAY).years_of_experience == 0


def test_overlapping_date_ranges_are_merged():
    text = "EXPERIENCE\nDeveloper at A  Jan 2020 - Dec 2021\nAnalyst at B  Jun 2021 - Jan 2023\n"
    assert extract.parse_resume_text(text + "w" * 60, TODAY).years_of_experience == 3


def test_date_formats_and_present():
    lines = ["03/2020 - 06/2022", "Aug 2022 to Present", "2019 - 2020"]
    assert extract.extract_years(lines, TODAY) == 5  # 27 + 23 + 12 months


def test_stated_years_of_experience_wins_when_larger():
    text = "Ravi Kumar\nSUMMARY\nBackend engineer with 7+ years of experience.\n" + "v" * 60
    assert extract.parse_resume_text(text, TODAY).years_of_experience == 7
    assert extract.extract_stated_years("Experience of 4 years in QA") == 4
    assert extract.extract_stated_years("no numbers here") == 0


def test_years_are_capped_at_two_digits():
    assert (
        extract.parse_resume_text("EXPERIENCE\n1900 - 2024\n" + "u" * 60, TODAY).years_of_experience
        == 99
    )


@pytest.mark.parametrize(
    ("education", "expected_start"),
    [
        (["B.Tech CSE, PES University", "M.Tech AI, IISc"], "M.Tech AI"),
        (["MBA, IIM Bangalore", "BBA, Christ University"], "MBA"),
        (["Ph.D. in Physics, IIT Madras", "M.Sc Physics"], "Ph.D."),
        (["Diploma in Electronics, GPT Hubli"], "Diploma"),
        (["B.E. Computer Science, VTU"], "B.E."),
        (["M.S. Data Science, UCSD"], "M.S."),
        (["10th, State Board", "12th, State Board"], "12th"),
        (["SSLC, State Board"], "SSLC"),
    ],
)
def test_highest_qualification(education, expected_start):
    assert extract.extract_qualification(education, []).startswith(expected_start)


def test_qualification_takes_institution_from_the_next_line():
    result = extract.extract_qualification(["Bachelor of Technology in CSE", "PES University"], [])
    assert result == "Bachelor of Technology in CSE, PES University"


def test_qualification_without_education_section_uses_strong_patterns_only():
    assert extract.extract_qualification([], ["I have a Bachelor of Science degree"]).startswith(
        "I have"
    )
    assert extract.extract_qualification([], ["Be a team player. ME and MS are letters"]) == ""


def test_roles_are_deduped_limited_and_skip_sentences():
    experience = [
        "Software Engineer at A  2020 - 2021",
        "software engineer, B",
        "Data Analyst | C",
        "Product Manager - D",
        "QA Tester at E",
        "UI Designer at F",
        "Site Reliability Engineer at G",
        "Developed internal tools for the engineer team",
        "- Led the developer onboarding",
        "Backend work with no title words",
    ]
    roles = extract.extract_roles(["Name", "Some Headline text"], [], experience)
    assert len(roles) == 5
    assert roles[0] == "Software Engineer"
    assert len({role.lower() for role in roles}) == 5
    assert not any(role.startswith(("Developed", "Led")) for role in roles)


def test_roles_from_objective_statements():
    roles = extract.extract_roles(
        ["Name"], ["Seeking a Data Analyst role at a fintech company."], []
    )
    assert roles == ["Data Analyst"]
    roles = extract.extract_roles(["Name"], ["Looking for the position of Project Manager."], [])
    assert roles == ["Project Manager"]


def test_name_handling():
    assert extract.extract_name(["RAVI KUMAR", "x"]) == "Ravi Kumar"
    assert extract.extract_name(["Resume", "ravi@example.com", "9876543210"]) == ""
    assert extract.extract_name(["Backend Developer", "Jane Doe"]) == "Jane Doe"


def test_fit_length_respects_appendix_b_limits():
    assert extract._fit_length(["aaaa", "bbbb", "cccc"], 10) == ["aaaa", "bbbb"]
    many = [f"skill{i:03d}" for i in range(200)]
    assert (
        len(", ".join(extract._fit_length(many, extract.MAX_SKILLS_CHARS)))
        <= extract.MAX_SKILLS_CHARS
    )


# ------------------------------------------------------------ reading files (#10, #13)


def test_reads_text_pdf_and_docx():
    for data, extension in ((make_pdf(SAMPLE_LINES), ".pdf"), (make_docx(SAMPLE_LINES), ".docx")):
        parsed = extract.parse_resume_file(data, extension, today=TODAY)
        assert parsed.full_name == "Huma Khan"
        assert "Python" in parsed.skills
        assert parsed.years_of_experience == 2


def test_docx_tables_are_read_in_order():
    data = make_docx(
        ["Jane Doe"], table_rows=[["SKILLS", "SKILLS"], ["Python, Docker", "Python, Docker"]]
    )
    text = extract.text_from_docx(data)
    assert "Python, Docker" in text
    assert text.count("Python, Docker") == 1  # merged cells are not repeated


def test_scanned_pdf_and_empty_docx_are_rejected():
    with pytest.raises(extract.ScannedResumeError) as info:
        extract.extract_text(make_pdf([]), ".pdf")
    assert "scanned" in str(info.value)
    with pytest.raises(extract.ScannedResumeError):
        extract.extract_text(make_docx(["Hi"]), ".docx")


def test_damaged_files_raise_a_readable_error():
    with pytest.raises(extract.ResumeParseError):
        extract.text_from_pdf(b"%PDF-1.4 this is not really a pdf")
    with pytest.raises(extract.ResumeParseError):
        extract.text_from_docx(b"PK\x03\x04 not a real docx")


# ------------------------------------------------------------------ upload (#9)


def _file(name, content, content_type="application/octet-stream"):
    return SimpleUploadedFile(name, content, content_type=content_type)


def test_validate_upload_rejects_a_file_that_grows_past_the_limit():
    fake = SimpleNamespace(
        name="cv.pdf", size=10, read=lambda n: b"x" * (upload.MAX_UPLOAD_BYTES + 1)
    )
    with pytest.raises(upload.ResumeUploadError) as info:
        upload.validate_upload(fake)
    assert info.value.code == "file_too_large"


@pytest.fixture
def seeker(db):
    return User.objects.create_user(
        username="seeker", email="seeker@example.com", password="Pass12345!"
    )


@pytest.fixture
def client(seeker):
    api = APIClient()
    api.force_authenticate(seeker)
    return api


def _post(client, upload_file):
    return client.post(URL, {"file": upload_file}, format="multipart")


@pytest.mark.django_db
def test_valid_pdf_is_accepted_and_the_profile_is_saved(client, seeker):
    response = _post(client, _file("cv.pdf", make_pdf(SAMPLE_LINES)))
    assert response.status_code == 201
    assert response.data["full_name"] == "Huma Khan"
    assert "Python" in response.data["skills"]
    profile = Profile.objects.get(user=seeker)
    assert profile.highest_qualification == "B.Tech CSE, PES University"
    assert profile.years_of_experience >= 2
    assert "Backend Developer" in profile.preferred_roles


@pytest.mark.django_db
def test_valid_docx_is_accepted_and_a_second_upload_updates_the_profile(client, seeker):
    assert _post(client, _file("cv.DOCX", make_docx(SAMPLE_LINES))).status_code == 201
    response = _post(client, _file("cv.docx", make_docx(SAMPLE_LINES)))
    assert response.status_code == 200
    assert Profile.objects.filter(user=seeker).count() == 1


@pytest.mark.django_db
def test_upload_keeps_saved_name_and_locations_the_resume_does_not_provide(client, seeker):
    Profile.objects.create(user=seeker, full_name="Saved Name", preferred_locations=["Pune"])
    lines = ["ravi@example.com", "SKILLS", "Python, Django, Docker", "x" * 60]
    response = _post(client, _file("cv.docx", make_docx(lines)))
    assert response.status_code == 200
    assert response.data["preferred_locations"] == ["Pune"]
    assert Profile.objects.get(user=seeker).full_name == "Saved Name"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("name", "content", "code"),
    [
        ("notes.txt", b"hello world", "invalid_type"),
        ("cv.exe", b"MZ....", "invalid_type"),
        ("cv", b"%PDF-1.4", "invalid_type"),
        ("fake.pdf", b"this is plain text", "invalid_type"),
        ("fake.docx", b"%PDF-1.4 not a docx", "invalid_type"),
        ("empty.pdf", b"", "empty_file"),
        ("big.pdf", b"%PDF-" + b"0" * upload.MAX_UPLOAD_BYTES, "file_too_large"),
    ],
)
def test_wrong_type_empty_or_oversized_files_are_rejected_with_a_message(
    client, name, content, code
):
    response = _post(client, _file(name, content))
    assert response.status_code == 400
    assert response.data["code"] == code
    assert response.data["error"]


@pytest.mark.django_db
def test_a_file_of_exactly_5_mb_is_not_rejected_for_size(client):
    data = b"%PDF-" + b"0" * (upload.MAX_UPLOAD_BYTES - 5)
    response = _post(client, _file("limit.pdf", data))
    assert response.status_code == 422  # passes validation, then fails to parse
    assert response.data["code"] == "unreadable_file"


@pytest.mark.django_db
def test_missing_file_field_is_rejected(client):
    response = client.post(URL, {}, format="multipart")
    assert response.status_code == 400
    assert response.data["code"] == "no_file"


@pytest.mark.django_db
def test_scanned_resume_gets_a_clear_422(client, seeker):
    response = _post(client, _file("scan.pdf", make_pdf([])))
    assert response.status_code == 422
    assert response.data["code"] == "scanned_resume"
    assert "text-based" in response.data["error"]
    assert not Profile.objects.filter(user=seeker).exists()


@pytest.mark.django_db
def test_anonymous_users_cannot_upload():
    response = APIClient().post(
        URL, {"file": _file("cv.pdf", make_pdf(SAMPLE_LINES))}, format="multipart"
    )
    assert response.status_code in (401, 403)

def test_get_profile(client, seeker):
    profile = Profile.objects.create(
        user=seeker,
        full_name="Test User",
        skills=["Python", "Django"],
        years_of_experience=1,
        highest_qualification="B.Tech",
        preferred_roles=["Software Developer"],
        preferred_locations=["Bangalore"],
    )

    response = client.get(PROFILE_URL)

    assert response.status_code == 200
    assert response.data["full_name"] == profile.full_name
    assert response.data["skills"] == ["Python", "Django"]
    assert response.data["preferred_roles"] == ["Software Developer"]


def test_update_profile(client, seeker):
    Profile.objects.create(
        user=seeker,
        full_name="Test User",
        skills=["Python"],
        years_of_experience=1,
        highest_qualification="B.Tech",
        preferred_roles=["Developer"],
        preferred_locations=["Bangalore"],
    )

    updated_data = {
        "full_name": "Updated User",
        "skills": ["Python", " Django ", "Python"],
        "years_of_experience": 2,
        "highest_qualification": "M.Tech",
        "preferred_roles": ["Backend Developer"],
        "preferred_locations": ["Bangalore", "Mysore"],
    }

    response = client.put(PROFILE_URL, updated_data, format="json")

    assert response.status_code == 200
    assert response.data["full_name"] == "Updated User"
    assert response.data["skills"] == ["Python", "Django"]
    assert response.data["preferred_roles"] == ["Backend Developer"]
    assert response.data["preferred_locations"] == ["Bangalore", "Mysore"]


def test_profile_requires_authentication():
    from rest_framework.test import APIClient

    response = APIClient().get(PROFILE_URL)

    assert response.status_code == 401


@pytest.mark.django_db
def test_profile_endpoint_returns_404_before_any_resume():
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient

    new = get_user_model().objects.create_user(username="fresh@pes.edu", email="fresh@pes.edu", password="x")
    client = APIClient()
    client.force_authenticate(new)
    assert client.get("/api/resume/profile/").status_code == 404
