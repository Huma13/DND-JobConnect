from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from matching.services import rescore_feed
from .models import Profile
from .serializers import ProfileSerializer


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return Profile.objects.get(user=self.request.user)

    def perform_update(self, serializer):
        profile = serializer.save()
        rescore_feed(self.request.user)