from rest_framework import serializers, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsAdminRole

from .models import ScheduledRun


class AdminRunSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = ScheduledRun
        fields = [
            "id", "user", "user_email", "trigger", "status", "platforms",
            "postings_found", "new_matches", "duplicates_hidden",
            "applications_submitted", "errors", "deferred", "started_at", "finished_at",
        ]
        read_only_fields = fields


class AdminRunViewSet(viewsets.ReadOnlyModelViewSet):
    """Issue #5 / SRS 6.5: automation run logs for the whole system, admin role only.

    GET /api/scheduler/admin/runs/?user=<id>&status=<status>&trigger=<trigger>&platform=<platform>
    """

    serializer_class = AdminRunSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        queryset = ScheduledRun.objects.select_related("user")
        params = self.request.query_params

        user_id = params.get("user")
        if user_id:
            if not user_id.isdigit():
                raise ValidationError({"user": "Must be a user id."})
            queryset = queryset.filter(user_id=int(user_id))

        for field, choices in (("status", ScheduledRun.Status), ("trigger", ScheduledRun.Trigger)):
            value = params.get(field)
            if value:
                if value not in choices.values:
                    raise ValidationError({field: f"Must be one of: {', '.join(choices.values)}."})
                queryset = queryset.filter(**{field: value})

        platform = params.get("platform")
        if platform:
            queryset = queryset.filter(platforms__contains=[platform])

        return queryset
