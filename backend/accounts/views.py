from rest_framework import generics, permissions
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import RegisterSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


@api_view(["POST"])
def pause_all(request):
    """SRS 6.2: stop scheduled and in-flight automation for this user."""
    paused = request.data.get("paused", True) in (True, "true", "1", 1)
    request.user.automation_paused = paused
    request.user.save(update_fields=["automation_paused"])
    return Response({"automation_paused": paused})
