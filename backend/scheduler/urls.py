from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("runs", views.RunViewSet, basename="run")

urlpatterns = [
    path("schedule/", views.schedule_view),
    path("rate-limits/", views.rate_limits_view),
] + router.urls
