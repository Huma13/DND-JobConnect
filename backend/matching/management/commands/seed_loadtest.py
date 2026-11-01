"""Create load-test users, each with a ranked feed (issue #43).

    python manage.py seed_loadtest --users 50 --postings 2000
"""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from matching.dedup import dedup_key
from matching.models import FeedItem, JobPosting
from resume_parser.models import Profile

ROLES = ["ML Engineer", "Backend Developer - Python", "Data Analyst", "Frontend Developer", "DevOps Engineer"]
COMPANIES = ["Razorpay", "Swiggy", "Infosys", "Zoho", "Flipkart", "TCS", "Freshworks", "Meesho", "CRED", "Wipro"]
CITIES = ["Bengaluru", "Hyderabad", "Pune", "Chennai", "Remote"]
PASSWORD = "LoadTest!2026"


class Command(BaseCommand):
    help = "Seed users and postings for Locust load tests."

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=50)
        parser.add_argument("--postings", type=int, default=2000)

    @transaction.atomic
    def handle(self, *args, users, postings, **opts):
        rng = random.Random(42)
        now = timezone.now()
        rows = []
        for i in range(postings):
            title, company = rng.choice(ROLES), rng.choice(COMPANIES)
            rows.append(JobPosting(
                platform=rng.choice(["linkedin", "naukri", "x"]), external_id=f"load-{i}",
                url=f"https://example.com/jobs/{i}", title=f"{title} {i % 40}", company=company,
                location=rng.choice(CITIES), description="Python SQL Docker 1-3 years",
                posted_at=now - timedelta(days=rng.randint(0, 30)), dedup_key=dedup_key(f"{title} {i % 40}", company),
            ))
        JobPosting.objects.bulk_create(rows, ignore_conflicts=True, batch_size=1000)
        posting_ids = list(JobPosting.objects.filter(external_id__startswith="load-").values_list("id", flat=True))

        User = get_user_model()
        for n in range(users):
            email = f"load{n}@jobconnect.test"
            user, created = User.objects.get_or_create(email=email, defaults={"username": email})
            if created:
                user.set_password(PASSWORD)
                user.save()
            Profile.objects.update_or_create(user=user, defaults=dict(
                skills=["Python", "SQL", "Docker"], years_of_experience=2,
                preferred_roles=[rng.choice(ROLES)], preferred_locations=["Bengaluru"]))
            FeedItem.objects.bulk_create(
                [FeedItem(user=user, posting_id=pid, relevance=rng.randint(0, 100)) for pid in posting_ids],
                ignore_conflicts=True, batch_size=2000)
        self.stdout.write(self.style.SUCCESS(
            f"Seeded {users} users x {len(posting_ids)} feed items. Password: {PASSWORD}"))
