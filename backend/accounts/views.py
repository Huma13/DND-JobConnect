from django.utils import timezone
from rest_framework import generics, permissions
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .disclaimer import DISCLAIMER_TEXT, DISCLAIMER_VERSION, has_accepted
from .gates import disclaimer_required
from .serializers import RegisterSerializer
from .models import PlatformCredential

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


@api_view(["GET", "POST"])
def pause_all(request):
    """SRS 6.2. POST stops scheduled and in-flight automation for this user.

    GET reports the current state so the UI can show it (issue #3).
    """
    if request.method == "POST":
        paused = request.data.get("paused", True) in (True, "true", "1", 1)
        request.user.automation_paused = paused
        request.user.save(update_fields=["automation_paused"])
    return Response({"automation_paused": request.user.automation_paused})


@api_view(["GET", "POST"])
def disclaimer_view(request):
    """Issue #4. GET shows the disclaimer; POST {"accept": true} accepts it."""
    user = request.user
    if request.method == "POST":
        if request.data.get("accept") not in (True, "true", "1", 1):
            return Response(
                {"detail": 'Send {"accept": true} to accept the disclaimer.'}, status=400
            )
        if not has_accepted(user):  # an earlier acceptance of this version keeps its date
            user.disclaimer_accepted_at = timezone.now()
            user.disclaimer_version = DISCLAIMER_VERSION
            user.save(update_fields=["disclaimer_accepted_at", "disclaimer_version"])
    accepted = has_accepted(user)
    return Response(
        {
            "version": DISCLAIMER_VERSION,
            "text": DISCLAIMER_TEXT,
            "accepted": accepted,
            "accepted_at": user.disclaimer_accepted_at if accepted else None,
            "required": disclaimer_required(),
        }
    )
