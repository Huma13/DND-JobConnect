from django.db import models


class Platform(models.TextChoices):
    LINKEDIN = "linkedin", "LinkedIn"
    X = "x", "X (Twitter)"
    NAUKRI = "naukri", "Naukri.com"
