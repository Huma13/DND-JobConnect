from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from matching.services import rescore_feed

from .models import Profile
from .serializers import ProfileSerializer


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        # 404 (not 500) until the user uploads a resume or creates a profile.
        return get_object_or_404(Profile, user=self.request.user)

    def perform_update(self, serializer):
        serializer.save()
        rescore_feed(self.request.user)
