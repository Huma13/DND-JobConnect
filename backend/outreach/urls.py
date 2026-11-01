from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("recruiters", views.RecruiterViewSet, basename="recruiter")
router.register("messages", views.MessageViewSet, basename="outreach-message")

urlpatterns = [path("limits/", views.limits_view)] + router.urls
