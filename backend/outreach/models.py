from django.conf import settings
from django.db import models

OUTREACH_PLATFORMS = ["linkedin", "x"]
DEFAULT_OUTREACH_LIMIT = 15  # REQ-16
LINKEDIN_NOTE_MAX = 300


class Recruiter(models.Model):
    """REQ-14: a person worth contacting about a posting."""

    posting = models.ForeignKey("matching.JobPosting", on_delete=models.CASCADE, related_name="recruiters")
    name = models.CharField(max_length=200)
    title = models.CharField(max_length=200, blank=True)
    linkedin_url = models.URLField(max_length=500, blank=True)
    x_handle = models.CharField(max_length=40, blank=True)
    reason = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    @property
    def best_channel(self) -> str:
        """X messages go through the API so they are preferred; LinkedIn notes are sent by hand."""
        return "x_message" if self.x_handle else "linkedin_note"


class OutreachSetting(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="outreach_settings")
    platform = models.CharField(max_length=20)
    daily_limit = models.PositiveSmallIntegerField(default=DEFAULT_OUTREACH_LIMIT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "platform"], name="uniq_outreach_setting")]


class OutreachMessage(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="outreach")
    recruiter = models.ForeignKey(Recruiter, on_delete=models.CASCADE, related_name="messages")
    platform = models.CharField(max_length=20)
    body = models.TextField()
    body_hash = models.CharField(max_length=64, blank=True, db_index=True)  # set when sent (REQ-17)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    detail = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "platform", "-sent_at"], name="outreach_limit_idx")]
