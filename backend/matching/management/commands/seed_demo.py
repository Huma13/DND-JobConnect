"""Create a ready-to-demo account: profile, ranked feed, and a few weeks of application history.

    DEMO_SOURCES=1 python manage.py seed_demo
    # log in as demo@dnd.test / Demo!2026

Safe to run again: it deletes the demo user's data and recreates it.
"""
import random
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.disclaimer import DISCLAIMER_VERSION
from applications.kit import build_kit
from applications.models import (
    Application,
    ApplicationAttempt,
    ApplicationResponse,
    ApplicationStatusHistory,
    ApplyKit,
)
from matching.models import FeedItem, SearchPreference
from matching.services import run_search
from resume_parser.models import Profile

EMAIL = "demo@dnd.test"
PASSWORD = "Demo!2026"

PROFILE = dict(
    full_name="Demo Student",
    skills=["Python", "Django", "PostgreSQL", "Docker", "SQL", "Machine Learning", "React"],
    years_of_experience=1,
    highest_qualification="B.Tech in Computer Science (AI & ML)",
    preferred_roles=["Backend Engineer", "ML Engineer", "Data Scientist", "SDE"],
    preferred_locations=["Bengaluru", "Hyderabad", "Remote"],
)

# (status, method, outcome) for the history; outcome is a response type or None.
HISTORY = [
    ("applied", "manual", "interview"),
    ("submitted", "ats", "reply"),
    ("submitted", "email", None),
    ("applied", "manual", None),
    ("manual_review_required", "ats", None),
    ("failed", "email", None),
    ("submitted", "ats", "interview"),
    ("applied", "manual", "reply"),
]


class Command(BaseCommand):
    help = "Seed a demo user with a ranked feed and application history."

    def handle(self, *args, **opts):
        if not settings.DEMO_SOURCES:
            raise CommandError("Set DEMO_SOURCES=1 so the feed is filled from the recorded postings.")
        user = self._reset_user()
        result = run_search(user, platforms=["linkedin", "naukri", "x"])
        self._history(user)
        self.stdout.write(self.style.SUCCESS(
            f"Demo ready: {result.new_feed_items} feed items ({result.duplicates} duplicates merged), "
            f"{Application.objects.filter(user=user).count()} applications.\n"
            f"Log in as {EMAIL} / {PASSWORD}"))

    @transaction.atomic
    def _reset_user(self):
        User = get_user_model()
        Application.objects.filter(user__email=EMAIL).delete()  # Application.kit is PROTECT
        User.objects.filter(email=EMAIL).delete()
        user = User.objects.create_user(username=EMAIL, email=EMAIL, password=PASSWORD,
                                        first_name="Demo", last_name="Student")
        user.disclaimer_accepted_at = timezone.now()
        user.disclaimer_version = DISCLAIMER_VERSION
        user.save(update_fields=["disclaimer_accepted_at", "disclaimer_version"])
        Profile.objects.create(user=user, **PROFILE)
        SearchPreference.objects.update_or_create(user=user, defaults={"platforms": ["linkedin", "naukri", "x"]})
        return user

    @transaction.atomic
    def _history(self, user):
        rng = random.Random(7)
        now = timezone.now()
        profile = user.profile
        items = list(FeedItem.objects.filter(user=user, duplicate_of__isnull=True)
                     .select_related("posting").order_by("-relevance")[len(HISTORY) // 2:])
        for (status, method, outcome), item in zip(HISTORY, items, strict=False):
            posting = item.posting
            when = now - timedelta(days=rng.randint(2, 20), hours=rng.randint(0, 8))
            kit = ApplyKit.objects.create(user=user, posting=posting, **build_kit(profile, user, posting))
            platform = {"manual": posting.platform, "ats": "greenhouse", "email": "email"}[method]
            app = Application.objects.create(
                user=user, posting=posting, kit=kit, method=method, platform=platform, status=status,
                to_email="careers@example.com" if method == "email" else "")
            Application.objects.filter(pk=app.pk).update(created_at=when, updated_at=when)
            if status != "applied":
                attempt = {"submitted": "success", "failed": "failure",
                           "manual_review_required": "captcha"}[status]
                a = ApplicationAttempt.objects.create(user=user, application=app, platform=platform, status=attempt)
                ApplicationAttempt.objects.filter(pk=a.pk).update(created_at=when)
            h = ApplicationStatusHistory.objects.create(application=app, user=user,
                                                        old_status="draft", new_status=status)
            ApplicationStatusHistory.objects.filter(pk=h.pk).update(changed_at=when)
            if outcome:
                r = ApplicationResponse.objects.create(application=app, user=user, response_type=outcome,
                                                       note="Recruiter replied by email.")
                ApplicationResponse.objects.filter(pk=r.pk).update(received_at=when + timedelta(days=3))
            item.state = FeedItem.State.APPLIED
            item.save(update_fields=["state"])
