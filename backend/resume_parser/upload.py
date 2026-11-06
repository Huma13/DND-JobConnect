"""Issue #9 (REQ-1): accept a resume upload (PDF or DOCX, up to 5 MB), then parse it (#10).

POST /api/resume/upload/   multipart/form-data, field name "file"

The file is read into memory, parsed and discarded. Only the extracted profile is stored
(SRS 3.2: the raw file is not kept after parsing).
"""

from datetime import date
from pathlib import Path

from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .extract import ResumeParseError, parse_resume_file
from .models import Profile

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # REQ-1
ALLOWED_TYPES = {".pdf": b"%PDF-", ".docx": b"PK\x03\x04"}  # extension -> file signature


class ResumeUploadError(Exception):
    """The upload itself is not acceptable (wrong type, too big, empty...)."""

    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


def validate_upload(upload) -> tuple[bytes, str]:
    """Check an uploaded file and return (its bytes, its lower-case extension)."""
    if upload is None:
        raise ResumeUploadError(
            "No file was uploaded. Send your resume in the 'file' field.", "no_file"
        )

    extension = Path(upload.name or "").suffix.lower()
    if extension not in ALLOWED_TYPES:
        raise ResumeUploadError("Only PDF and DOCX files are accepted.", "invalid_type")
    if upload.size == 0:
        raise ResumeUploadError("The file is empty. Please upload your resume.", "empty_file")

    too_large = ResumeUploadError(
        "The file is larger than 5 MB. Please upload a smaller file.", "file_too_large"
    )
    if upload.size > MAX_UPLOAD_BYTES:
        raise too_large
    data = upload.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise too_large

    if not data.startswith(ALLOWED_TYPES[extension]):
        raise ResumeUploadError(
            f"The file does not look like a real {extension[1:].upper()} file.", "invalid_type"
        )
    return data, extension


@api_view(["POST"])
@parser_classes([MultiPartParser])
@permission_classes([IsAuthenticated])
def upload_resume(request):
    try:
        data, extension = validate_upload(request.FILES.get("file"))
    except ResumeUploadError as exc:
        return Response({"error": str(exc), "code": exc.code}, status=400)

    try:
        parsed = parse_resume_file(data, extension, today=date.today())  # REQ-2, REQ-4
    except ResumeParseError as exc:
        return Response({"error": str(exc), "code": exc.code}, status=422)

    fields = parsed.to_dict()
    if not fields["full_name"]:
        del fields["full_name"]  # keep a name that is already saved rather than blank it
    profile, created = Profile.objects.update_or_create(user=request.user, defaults=fields)

    return Response(
        {**parsed.to_dict(), "preferred_locations": profile.preferred_locations},
        status=201 if created else 200,
    )
