from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

urlpatterns = [
    path("register/", views.RegisterView.as_view()),
    path("login/", TokenObtainPairView.as_view()),
    path("refresh/", TokenRefreshView.as_view()),
    path("pause/", views.pause_all),
    path("disclaimer/", views.disclaimer_view),
]
