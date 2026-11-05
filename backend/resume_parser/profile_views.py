
from django.db import transaction
from rest_framework import generics, permissions

from matching.services import rescore_feed

from .models import Profile
from .serializers import ProfileSerializer


class ProfileDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile, _ = Profile.objects.get_or_create(user=self.request.user)
        return profile

    def perform_update(self, serializer):
        with transaction.atomic():
            serializer.save()
            rescore_feed(self.request.user)
