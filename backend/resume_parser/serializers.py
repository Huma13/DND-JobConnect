
from rest_framework import serializers

from .models import Profile


class ProfileSerializer(serializers.ModelSerializer):
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

    def validate_skills(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Skills must be a list.")

        if not all(isinstance(item, str) and item.strip() for item in value):
            raise serializers.ValidationError(
                "Every skill must be a non-empty string."
            )

        return [item.strip() for item in value]

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

        return [item.strip() for item in value]
