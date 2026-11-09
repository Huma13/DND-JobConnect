import pytest
from django.core import mail
from django.db import transaction

from applications.models import Notification
from applications.notifications import create_notification


@pytest.fixture(autouse=True)
def use_test_email_backend(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.DEFAULT_FROM_EMAIL = "notifications@test.com"
    mail.outbox.clear()


@pytest.mark.django_db(transaction=True)
def test_create_notification_saves_and_sends_email(user):
    notification = create_notification(
        user=user,
        kind="new_matches",
        message="Your search found 3 new job matches.",
        email_subject="New Job Matches",
    )

    assert Notification.objects.filter(pk=notification.pk).exists()
    assert notification.user == user
    assert notification.kind == "new_matches"
    assert notification.read is False

    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "New Job Matches"
    assert mail.outbox[0].to == [user.email]


@pytest.mark.django_db(transaction=True)
def test_email_is_sent_only_after_transaction_commits(user):
    with transaction.atomic():
        create_notification(
            user=user,
            kind="run_result",
            message="Your search run is complete.",
        )

        # Email must wait until the transaction commits.
        assert len(mail.outbox) == 0

    assert len(mail.outbox) == 1


@pytest.mark.django_db(transaction=True)
def test_rolled_back_transaction_does_not_send_email(user):
    with transaction.atomic():
        create_notification(
            user=user,
            kind="status_change",
            message="Your application status has changed.",
        )

        transaction.set_rollback(True)

    assert len(mail.outbox) == 0
    assert Notification.objects.filter(
        user=user,
        kind="status_change",
    ).count() == 0
