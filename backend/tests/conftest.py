import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from resume_parser.models import Profile


@pytest.fixture(autouse=True)
def _settings(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.COLLECTOR_MIN_DELAY_SECONDS = 0
    from config.celery import app
    app.conf.task_always_eager = True


def make_user(email="seeker@pes.edu", **profile):
    user = get_user_model().objects.create_user(username=email, email=email, password="Str0ng!pass9")
    defaults = dict(skills=["Python", "PyTorch", "SQL", "Docker"], years_of_experience=2,
                    preferred_roles=["ML Engineer"], preferred_locations=["Bengaluru"])
    defaults.update(profile)
    Profile.objects.create(user=user, **defaults)
    return user


@pytest.fixture
def user(db):
    return make_user()


@pytest.fixture
def api(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    client.user = user
    return client
