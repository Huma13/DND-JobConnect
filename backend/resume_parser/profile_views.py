
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions

from matching.services import rescore_feed

from .models import Profile
from .serializers import ProfileSerializer


class ProfileDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return get_object_or_404(Profile, user=self.request.user)

    def perform_update(self, serializer):
        with transaction.atomic():
            serializer.save()
            rescore_feed(self.request.user)
