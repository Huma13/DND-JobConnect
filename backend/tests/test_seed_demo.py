"""seed_demo builds a demo account with a ranked feed and application history."""
import pytest
from django.core.management import CommandError, call_command

from applications.models import Application, ApplicationResponse
from matching.models import FeedItem


@pytest.mark.django_db
def test_seed_demo_requires_demo_sources(settings):
    settings.DEMO_SOURCES = False
    with pytest.raises(CommandError):
        call_command("seed_demo")


@pytest.mark.django_db
def test_seed_demo_creates_feed_and_history_and_can_rerun(settings, django_user_model):
    settings.DEMO_SOURCES = True
    call_command("seed_demo")
    call_command("seed_demo")  # idempotent

    user = django_user_model.objects.get(email="demo@dnd.test")
    assert user.check_password("Demo!2026")
    assert FeedItem.objects.filter(user=user, state="new").exists()
    assert Application.objects.filter(user=user).count() == 8
    assert ApplicationResponse.objects.filter(user=user, response_type="interview").exists()


@pytest.mark.django_db
def test_seed_demo_connects_a_local_mailbox(settings):
    from applications.models import MailboxConfig

    settings.DEMO_SOURCES = True
    settings.DEMO_SMTP_HOST = "mailpit"
    call_command("seed_demo")
    box = MailboxConfig.objects.get(user__email="demo@dnd.test")
    assert (box.host, box.port, box.use_tls) == ("mailpit", 1025, False)
