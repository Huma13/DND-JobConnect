from rest_framework import serializers

from applications.models import ApplicationResponse


class ApplicationResponseSerializer(serializers.ModelSerializer):
    """Serializer for employer replies and interview invitations."""

    class Meta:
        model = ApplicationResponse
        fields = [
            "id",
            "application",
            "response_type",
            "note",
            "received_at",
        ]
        read_only_fields = ["id", "application", "received_at"]
