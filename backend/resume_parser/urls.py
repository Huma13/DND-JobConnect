from django.urls import path

from .profile_tips_view import profile_tips
from .profile_views import ProfileDetailView

urlpatterns = [
    path("tips/", profile_tips, name="profile-tips"),
    path("profile/", ProfileDetailView.as_view(), name="profile"),
]
