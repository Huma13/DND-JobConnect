"""View for issue #12: profile improvement tips.

POST /resume/tips/   (JSON body)
    {
      "resume_text": "...",
      "postings": ["job description 1", "job description 2"],
      "target_role": "backend engineer",
      "current_headline": "",   # optional
      "current_summary": ""     # optional
    }

Any field left out falls back to the logged-in user's profile (if your
profile model has resume_text / target_role / headline / summary fields).
"""
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .profile_tips import generate_profile_tips


def _profile_value(user, name):
    profile = getattr(user, "profile", None)
    return getattr(profile, name, "") or ""


@csrf_exempt  # remove if you use Django session auth with CSRF tokens
@require_POST
def profile_tips(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Login required."}, status=401)

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    resume_text = data.get("resume_text") or _profile_value(request.user, "resume_text")
    target_role = data.get("target_role") or _profile_value(request.user, "target_role")
    postings = data.get("postings") or []

    if not target_role:
        return JsonResponse({"error": "target_role is required."}, status=400)
    if not isinstance(postings, list):
        return JsonResponse({"error": "postings must be a list of strings."}, status=400)

    tips = generate_profile_tips(
        resume_text=resume_text,
        target_postings=[str(p) for p in postings],
        target_role=target_role,
        current_headline=data.get("current_headline") or _profile_value(request.user, "headline"),
        current_summary=data.get("current_summary") or _profile_value(request.user, "summary"),
    )
    return JsonResponse(tips.to_dict())
