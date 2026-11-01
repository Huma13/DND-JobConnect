from django.conf import settings
from django.db import models

from core.choices import Platform


def default_platforms():
    return [p.value for p in Platform]


class SearchPreference(models.Model):
    """REQ-5: which sources a user wants searched."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="search_pref")
    platforms = models.JSONField(default=default_platforms)


class JobPosting(models.Model):
    platform = models.CharField(max_length=20, choices=Platform.choices)
    external_id = models.CharField(max_length=200)
    url = models.URLField(max_length=1000)
    title = models.CharField(max_length=300)
    company = models.CharField(max_length=300)
    location = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    skills = models.JSONField(default=list)
    posted_at = models.DateTimeField(null=True, blank=True)
    dedup_key = models.CharField(max_length=64, db_index=True)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["platform", "external_id"], name="uniq_platform_posting")]


class FeedItem(models.Model):
    """A posting in one user's feed with its relevance score (REQ-6)."""

    class State(models.TextChoices):
        NEW = "new", "New"
        SKIPPED = "skipped", "Skipped"
        APPLIED = "applied", "Applied"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="feed")
    posting = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name="feed_items")
    relevance = models.PositiveSmallIntegerField()
    # REQ-7: a duplicate points at the item the user actually sees.
    duplicate_of = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE,
                                     related_name="duplicates")
    state = models.CharField(max_length=10, choices=State.choices, default=State.NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-relevance", "-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "posting"], name="uniq_user_posting")]
        indexes = [models.Index(fields=["user", "duplicate_of", "-relevance"], name="feed_user_rank_idx")]
