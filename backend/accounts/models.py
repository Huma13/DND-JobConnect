from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Minimal user model. Auth/RBAC stories are owned by the Platform Foundation epic."""

    class Role(models.TextChoices):
        JOB_SEEKER = "job_seeker", "Job Seeker"
        ADMIN = "admin", "System Administrator"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.JOB_SEEKER)
    automation_paused = models.BooleanField(default=False)  # SRS 6.2 Pause All
    # Issue #4 / SRS section 7: the legal disclaimer must be accepted before automation runs.
    disclaimer_accepted_at = models.DateTimeField(null=True, blank=True)
    disclaimer_version = models.CharField(max_length=20, blank=True, default="")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]
