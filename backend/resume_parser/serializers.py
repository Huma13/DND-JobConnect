from rest_framework import serializers

from .models import Profile


class ProfileSerializer(serializers.ModelSerializer):
    skills = serializers.ListField(
        child=serializers.CharField(max_length=100, allow_blank=False),
        allow_empty=True,
    )
    preferred_roles = serializers.ListField(
        child=serializers.CharField(max_length=100, allow_blank=False),
        allow_empty=False,
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
        ]

    def validate_years_of_experience(self, value):
        if value > 99:
            raise serializers.ValidationError(
                "Years of experience cannot exceed 99."
            )
        return value

    def validate(self, attrs):
        for field in ("skills", "preferred_roles", "preferred_locations"):
            if field in attrs:
                attrs[field] = list(
                    dict.fromkeys(item.strip() for item in attrs[field])
                )
        return attrs
