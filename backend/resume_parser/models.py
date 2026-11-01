from django.conf import settings
from django.db import models


class Profile(models.Model):
    """Appendix B profile. Parsing (REQ-1..4) is owned by the Resume Parsing epic;
    matching only reads these fields."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    full_name = models.CharField(max_length=100, blank=True)
    skills = models.JSONField(default=list)
    years_of_experience = models.PositiveSmallIntegerField(default=0)
    highest_qualification = models.CharField(max_length=150, blank=True)
    preferred_roles = models.JSONField(default=list)
    preferred_locations = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)
