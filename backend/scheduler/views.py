from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import beat
from .models import Schedule, ScheduledRun
from .ratelimit import usage
from .serializers import ScheduledRunSerializer, ScheduleSerializer


@api_view(["GET", "PUT", "DELETE"])
def schedule_view(request):
    """REQ-18: one daily/weekly schedule per user."""
    current = Schedule.objects.filter(user=request.user).first()
    if request.method == "GET":
        if current is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(ScheduleSerializer(current).data)
    if request.method == "DELETE":
        with transaction.atomic():
            beat.remove(request.user.pk)
            Schedule.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    ser = ScheduleSerializer(current, data=request.data)
    ser.is_valid(raise_exception=True)
    with transaction.atomic():
        schedule = ser.save(user=request.user)
        schedule.periodic_task = beat.sync(schedule)
        schedule.save(update_fields=["periodic_task"])
    return Response(ScheduleSerializer(schedule).data,
                    status=status.HTTP_200_OK if current else status.HTTP_201_CREATED)


class RunViewSet(viewsets.ReadOnlyModelViewSet):
    """REQ-20: run log."""

    serializer_class = ScheduledRunSerializer

    def get_queryset(self):
        return ScheduledRun.objects.filter(user=self.request.user)


@api_view(["GET"])
def rate_limits_view(request):
    """REQ-19: current usage per platform window."""
    return Response(usage(request.user))
