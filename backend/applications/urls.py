from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("kits", views.KitViewSet, basename="kit")
router.register("attempts", views.AttemptViewSet, basename="attempt")
router.register("notifications", views.NotificationViewSet, basename="notification")
router.register("", views.ApplicationViewSet, basename="application")

urlpatterns = [
    path("limits/", views.limits_view),
    path("mailbox/", views.MailboxView.as_view()),
] + router.urls
