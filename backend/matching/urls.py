from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("feed", views.FeedViewSet, basename="feed")

urlpatterns = [path("preferences/", views.SearchPreferenceView.as_view())] + router.urls
