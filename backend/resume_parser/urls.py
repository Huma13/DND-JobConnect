from django.urls import path

from .profile_tips_view import profile_tips

urlpatterns = [
    path("tips/", profile_tips, name="profile-tips"),
]
