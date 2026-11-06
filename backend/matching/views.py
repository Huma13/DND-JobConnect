from django.db.models import Prefetch
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.gates import disclaimer_accepted, disclaimer_required_response
from scheduler.models import ScheduledRun
from scheduler.tasks import search_task

from .filters import FeedFilter
from .models import FeedItem, SearchPreference
from .serializers import FeedItemSerializer, SearchPreferenceSerializer


class SearchPreferenceView(generics.RetrieveUpdateAPIView):
    """REQ-5: GET/PUT which platforms to search."""

    serializer_class = SearchPreferenceSerializer

    def get_object(self):
        return SearchPreference.objects.get_or_create(user=self.request.user)[0]


class FeedViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """REQ-6/7/8: ranked, de-duplicated, filterable feed."""

    serializer_class = FeedItemSerializer
    filterset_class = FeedFilter

    def get_queryset(self):
        dupes = FeedItem.objects.select_related("posting")
        qs = (FeedItem.objects.filter(user=self.request.user, duplicate_of__isnull=True)
              .select_related("posting")
              .prefetch_related(Prefetch("duplicates", queryset=dupes))
              .order_by("-relevance", "-created_at", "-id"))
        if "state" not in self.request.query_params:
            qs = qs.exclude(state=FeedItem.State.SKIPPED)
        return qs

    @action(detail=True, methods=["post"])
    def skip(self, request, pk=None):
        item = self.get_object()
        item.state = FeedItem.State.SKIPPED
        item.save(update_fields=["state"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"])
    def search(self, request):
        """Start a manual search now. Runs in the worker; poll the run for results."""
        if request.user.automation_paused:
            return Response({"detail": "Automation is paused."}, status=status.HTTP_409_CONFLICT)
        if not disclaimer_accepted(request.user):
            return disclaimer_required_response()
        active = ScheduledRun.objects.filter(user=request.user, status=ScheduledRun.Status.RUNNING).first()
        if active:
            return Response({"run_id": active.pk, "detail": "A search is already running."},
                            status=status.HTTP_409_CONFLICT)
        run = ScheduledRun.objects.create(user=request.user, trigger=ScheduledRun.Trigger.MANUAL)
        search_task.delay(request.user.pk, run_id=run.pk)
        return Response({"run_id": run.pk}, status=status.HTTP_202_ACCEPTED)
