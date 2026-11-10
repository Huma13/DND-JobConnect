"""SRS 6.1 load test (issue #43, TC-30..TC-32).

Seed first:  python manage.py seed_loadtest --users 50 --postings 2000
Run:         locust -f loadtest/locustfile.py --host http://localhost:8000
Or use loadtest/run_degradation.py for the pass/fail check.
"""
import itertools
import random
from datetime import date, timedelta

from locust import HttpUser, between, task

_ids = itertools.count()
PASSWORD = "LoadTest!2026"


class JobSeeker(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        email = f"load{next(_ids) % 50}@jobconnect.test"
        r = self.client.post("/api/auth/login/", json={"email": email, "password": PASSWORD}, name="login")
        r.raise_for_status()
        self.client.headers["Authorization"] = f"Bearer {r.json()['access']}"

    @task(6)
    def feed(self):
        self.client.get("/api/jobs/feed/", name="feed")

    @task(4)
    def filtered_feed(self):
        platform = random.choice(["linkedin", "naukri", "x"])
        self.client.get(f"/api/jobs/feed/?platform={platform}&min_score=60&posted_within_days=7&location=bengal",
                        name="feed (filtered)")

    @task(2)
    def feed_page(self):
        self.client.get(f"/api/jobs/feed/?page={random.randint(2, 20)}", name="feed (page n)")

    @task(2)
    def runs(self):
        self.client.get("/api/scheduler/runs/", name="run log")

    @task(1)
    def rate_limits(self):
        self.client.get("/api/scheduler/rate-limits/", name="rate limits")

    @task(1)
    def dashboard(self):
        # TC-31: the analytics dashboard loads these three endpoints together.
        end = date.today()
        start = end - timedelta(days=30)
        self.client.get(f"/api/applications/statistics/?start_date={start}&end_date={end}",
                        name="dashboard: statistics")
        self.client.get("/api/applications/response-analytics/", name="dashboard: response rate")
        self.client.get("/api/applications/", name="dashboard: history")
