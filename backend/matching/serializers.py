from rest_framework import serializers

from core.choices import Platform

from .models import FeedItem, SearchPreference


class SearchPreferenceSerializer(serializers.ModelSerializer):
    platforms = serializers.ListField(child=serializers.ChoiceField(choices=Platform.choices),
                                      allow_empty=False, max_length=3)

    class Meta:
        model = SearchPreference
        fields = ["platforms"]

    def validate_platforms(self, value):
        return sorted(set(value))


class FeedItemSerializer(serializers.ModelSerializer):
    platform = serializers.CharField(source="posting.platform")
    title = serializers.CharField(source="posting.title")
    company = serializers.CharField(source="posting.company")
    location = serializers.CharField(source="posting.location")
    url = serializers.URLField(source="posting.url")
    posted_at = serializers.DateTimeField(source="posting.posted_at")
    is_duplicate = serializers.SerializerMethodField()
    also_on = serializers.SerializerMethodField()

    class Meta:
        model = FeedItem
        fields = ["id", "platform", "title", "company", "location", "url", "posted_at",
                  "relevance", "state", "is_duplicate", "also_on", "created_at"]

    def get_is_duplicate(self, obj) -> bool:
        return bool(obj.duplicates.all())

    def get_also_on(self, obj) -> list[dict]:
        return [{"platform": d.posting.platform, "url": d.posting.url}
                for d in obj.duplicates.all() if d.posting.platform != obj.posting.platform
                or d.posting.url != obj.posting.url]
