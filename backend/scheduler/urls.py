from django.urls import path
from rest_framework.routers import DefaultRouter

from . import admin_views, views

router = DefaultRouter()
router.register("runs", views.RunViewSet, basename="run")
router.register("admin/runs", admin_views.AdminRunViewSet, basename="admin-run")

urlpatterns = [
    path("schedule/", views.schedule_view),
    path("rate-limits/", views.rate_limits_view),
] + router.urls
