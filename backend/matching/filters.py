"""REQ-8 feed filters: platform, location, minimum score, recency."""
from datetime import timedelta

import django_filters
from django.utils import timezone

from core.choices import Platform

from .models import FeedItem


class FeedFilter(django_filters.FilterSet):
    platform = django_filters.MultipleChoiceFilter(field_name="posting__platform", choices=Platform.choices)
    location = django_filters.CharFilter(field_name="posting__location", lookup_expr="icontains")
    min_score = django_filters.NumberFilter(field_name="relevance", lookup_expr="gte", min_value=0, max_value=100)
    posted_within_days = django_filters.NumberFilter(method="filter_recency", min_value=1, max_value=365)
    state = django_filters.MultipleChoiceFilter(choices=FeedItem.State.choices)

    class Meta:
        model = FeedItem
        fields = ["platform", "location", "min_score", "posted_within_days", "state"]

    def filter_recency(self, qs, name, value):
        cutoff = timezone.now() - timedelta(days=int(value))
        # Postings with no date fall back to when we first saw them.
        return qs.filter(posting__posted_at__gte=cutoff) | qs.filter(
            posting__posted_at__isnull=True, created_at__gte=cutoff)
