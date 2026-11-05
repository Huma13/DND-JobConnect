from django.conf import settings
from django.db import models

from core.choices import Platform

# Channels an application can go through. ATS and email are not job boards but still get their own limits.
APPLY_PLATFORMS = [*Platform.values, "greenhouse", "lever", "email"]
APPLY_PLATFORM_CHOICES = [*Platform.choices, ("greenhouse", "Greenhouse"), ("lever", "Lever"), ("email", "Email")]
DEFAULT_DAILY_LIMIT = 20  # REQ-11


class ApplySetting(models.Model):
    """REQ-10, REQ-11: per-platform daily limit and Full-Auto switch."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="apply_settings")
    platform = models.CharField(max_length=20, choices=APPLY_PLATFORM_CHOICES)
    daily_limit = models.PositiveSmallIntegerField(default=DEFAULT_DAILY_LIMIT)
    full_auto = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "platform"], name="uniq_apply_setting")]


class ApplyKit(models.Model):
    """REQ-9: tailored resume, cover letter and answers for one posting."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="kits")
    posting = models.ForeignKey("matching.JobPosting", on_delete=models.CASCADE, related_name="kits")
    resume_text = models.TextField()
    cover_letter = models.TextField()
    answers = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class Application(models.Model):
    class Method(models.TextChoices):
        MANUAL = "manual", "Assisted (LinkedIn/Naukri)"
        ATS = "ats", "Career page (Greenhouse/Lever)"
        EMAIL = "email", "Email"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPLIED = "applied", "Applied (marked by user)"
        SUBMITTED = "submitted", "Submitted"
        FAILED = "failed", "Failed"
        MANUAL_REVIEW = "manual_review_required", "Manual Review Required"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications")
    posting = models.ForeignKey("matching.JobPosting", on_delete=models.CASCADE, related_name="applications")
    kit = models.ForeignKey(ApplyKit, on_delete=models.PROTECT, related_name="applications")
    method = models.CharField(max_length=10, choices=Method.choices)
    platform = models.CharField(max_length=20, choices=APPLY_PLATFORM_CHOICES)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    to_email = models.EmailField(blank=True)
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class ApplicationAttempt(models.Model):
    """REQ-12: every attempt, with a timestamp and a status."""

    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILURE = "failure", "Failure"
        CAPTCHA = "captcha", "CAPTCHA"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attempts")
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="attempts")
    platform = models.CharField(max_length=20, choices=APPLY_PLATFORM_CHOICES)
    status = models.CharField(max_length=10, choices=Status.choices)
    detail = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "platform", "-created_at"], name="attempt_limit_idx")]


class Notification(models.Model):
    """REQ-13: tells the user an application needs them (for example a CAPTCHA)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=30)
    message = models.CharField(max_length=300)
    application = models.ForeignKey(Application, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class MailboxConfig(models.Model):
    """REQ-9 email apply: the user's own SMTP mailbox. The password is stored encrypted."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mailbox")
    host = models.CharField(max_length=200)
    port = models.PositiveIntegerField(default=587)
    username = models.CharField(max_length=200)
    password_encrypted = models.TextField()
    from_email = models.EmailField()
    use_tls = models.BooleanField(default=True)


class ApplicationStatusHistory(models.Model):
    """Records every manual status change made to an application."""

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="application_status_changes",
    )
    old_status = models.CharField(max_length=30, choices=Application.Status.choices)
    new_status = models.CharField(max_length=30, choices=Application.Status.choices)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at", "-id"]

    def __str__(self):
        return f"Application {self.application_id}: {self.old_status} -> {self.new_status}"


class ApplicationResponse(models.Model):
    """REQ-23: Track employer replies and interview invitations."""

    class Type(models.TextChoices):
        REPLY = "reply", "Employer Reply"
        INTERVIEW = "interview", "Interview Invitation"

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="employer_responses",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="application_responses",
    )
    response_type = models.CharField(max_length=20, choices=Type.choices)
    note = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at", "-id"]

    def __str__(self):
        return f"{self.application_id} - {self.response_type}"
