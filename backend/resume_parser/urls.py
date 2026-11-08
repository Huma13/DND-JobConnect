from django.urls import path

from .profile_tips_view import profile_tips
from .upload import upload_resume
from .profile_views import ProfileView

urlpatterns = [
    path("tips/", profile_tips, name="profile-tips"),
    path("upload/", upload_resume, name="resume-upload"),
    path("profile/", ProfileView.as_view(), name="profile"),
]