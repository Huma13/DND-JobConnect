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

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]
