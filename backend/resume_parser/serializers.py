
from rest_framework import serializers

from .models import Profile


class ProfileSerializer(serializers.ModelSerializer):
    skills = serializers.ListField(
        child=serializers.CharField(max_length=100, allow_blank=False),
        allow_empty=True,
    )
    preferred_roles = serializers.ListField(
        child=serializers.CharField(max_length=100, allow_blank=False),
        allow_empty=True,
    )
    preferred_locations = serializers.ListField(
        child=serializers.CharField(max_length=100, allow_blank=False),
        allow_empty=True,
    )

    class Meta:
        model = Profile
        fields = [
            "full_name",
            "skills",
            "years_of_experience",
            "highest_qualification",
            "preferred_roles",
            "preferred_locations",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def validate_years_of_experience(self, value):
        if value > 99:
            raise serializers.ValidationError(
                "Years of experience cannot exceed 99."
            )
        return value

    def validate_skills(self, value):
        return self.validate_string_list(value, "Skills")

    def validate_preferred_roles(self, value):
        return self.validate_string_list(value, "Preferred roles")

    def validate_preferred_locations(self, value):
        return self.validate_string_list(value, "Preferred locations")

    @staticmethod
    def validate_string_list(value, field_name):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                f"{field_name} must be a list."
            )

        if not all(isinstance(item, str) and item.strip() for item in value):
            raise serializers.ValidationError(
                f"Every {field_name.lower()} entry must be a non-empty string."
            )

        return list(dict.fromkeys(item.strip() for item in value))
