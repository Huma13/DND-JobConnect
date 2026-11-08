from django.urls import path

from .profile_tips_view import profile_tips
from .profile_views import ProfileView
from .upload import upload_resume

urlpatterns = [
    path("tips/", profile_tips, name="profile-tips"),
    path("upload/", upload_resume, name="resume-upload"),
    path("profile/", ProfileView.as_view(), name="profile"),
]
