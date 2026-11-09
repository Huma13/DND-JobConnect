import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from .models import Notification

log = logging.getLogger(__name__)


def create_notification(user, kind, message, application=None, email_subject=None):
    """Create an in-app notification and send a corresponding email."""

    notification = Notification.objects.create(
        user=user,
        kind=kind,
        message=message,
        application=application,
    )

    if user.email:
        def send_notification_email():
            try:
                send_mail(
                    subject=email_subject or "DND JobConnect Notification",
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except Exception:
                log.exception(
                    "Failed to send notification email to user %s",
                    user.pk,
                )

        transaction.on_commit(send_notification_email)

    return notification