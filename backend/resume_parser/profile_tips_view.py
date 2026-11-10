"""Issue #12: profile improvement tips.

POST /api/resume/tips/   (JSON body, every field optional)
    {
      "target_role": "backend engineer",       # default: first preferred role
      "resume_text": "...",                     # default: the profile's skills and qualification
      "postings": ["job description 1", ...],   # default: the user's top feed postings
      "current_headline": "",
      "current_summary": ""
    }

A DRF view so the web app's JWT login works (a plain Django view only sees session logins).
"""
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from matching.models import FeedItem

from .models import Profile
from .profile_tips import generate_profile_tips

DEFAULT_POSTINGS = 20


def _resume_text(profile: Profile | None) -> str:
    if profile is None:
        return ""
    parts = [*profile.skills, profile.highest_qualification, *profile.preferred_roles]
    return ", ".join(p for p in parts if p)


def _feed_postings(user, limit: int = DEFAULT_POSTINGS) -> list[str]:
    items = (FeedItem.objects.filter(user=user, duplicate_of__isnull=True)
             .select_related("posting").order_by("-relevance")[:limit])
    return [f"{i.posting.title}. {i.posting.description} {' '.join(i.posting.skills)}" for i in items]


@api_view(["POST"])
def profile_tips(request):
    data = request.data if isinstance(request.data, dict) else {}
    profile = Profile.objects.filter(user=request.user).first()

    target_role = data.get("target_role") or (profile.preferred_roles[0] if profile and profile.preferred_roles else "")
    if not target_role:
        return Response({"error": "target_role is required (or add a preferred role to your profile)."},
                        status=status.HTTP_400_BAD_REQUEST)
    postings = data.get("postings")
    if postings is None:
        postings = _feed_postings(request.user)
    if not isinstance(postings, list):
        return Response({"error": "postings must be a list of strings."}, status=status.HTTP_400_BAD_REQUEST)

    tips = generate_profile_tips(
        resume_text=data.get("resume_text") or _resume_text(profile),
        target_postings=[str(p) for p in postings],
        target_role=target_role,
        current_headline=data.get("current_headline") or "",
        current_summary=data.get("current_summary") or "",
    )
    return Response(tips.to_dict())
