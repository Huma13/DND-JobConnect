"""Application Manager (SAD): limits, confirmation, submission, attempt log and CAPTCHA handling."""
from __future__ import annotations

import base64
import hashlib
import logging
from datetime import timedelta

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from django.utils import timezone

from integrations.ats import get_ats_adapter
from integrations.base import CaptchaDetected, SubmitError
from matching.models import FeedItem

from .models import (
    DEFAULT_DAILY_LIMIT,
    Application,
    ApplicationAttempt,
    ApplySetting,
    MailboxConfig,
    Notification,
)

log = logging.getLogger(__name__)


class Blocked(Exception):
    def __init__(self, detail: str, status: int):
        super().__init__(detail)
        self.detail, self.status = detail, status


# ---- settings, limits (REQ-10, REQ-11) -------------------------------------------

def get_setting(user, platform: str) -> ApplySetting:
    return ApplySetting.objects.get_or_create(user=user, platform=platform)[0]


def _day_start():
    return timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)


def used_today(user, platform: str) -> int:
    start = _day_start()
    return ApplicationAttempt.objects.filter(user=user, platform=platform, created_at__gte=start,
                                             created_at__lt=start + timedelta(days=1)).count()


def check_limit(user, platform: str) -> None:
    limit = ApplySetting.objects.filter(user=user, platform=platform).values_list("daily_limit", flat=True).first()
    limit = DEFAULT_DAILY_LIMIT if limit is None else limit
    if used_today(user, platform) >= limit:
        raise Blocked(f"Daily limit of {limit} applications on {platform} reached.", 429)


# ---- attempt log (REQ-12) ---------------------------------------------------------

def record_attempt(app: Application, status: str, detail: str = "") -> ApplicationAttempt:
    return ApplicationAttempt.objects.create(user=app.user, application=app, platform=app.platform,
                                             status=status, detail=detail[:300])


def _mark_feed_applied(app: Application) -> None:
    FeedItem.objects.filter(user=app.user, posting=app.posting).update(state=FeedItem.State.APPLIED)


# ---- confirmation gate (REQ-10) ---------------------------------------------------

def requires_confirmation(user, platform: str) -> bool:
    return not ApplySetting.objects.filter(user=user, platform=platform, full_auto=True).exists()


# ---- email (own mailbox) ----------------------------------------------------------

def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest()))


def encrypt_password(raw: str) -> str:
    return _fernet().encrypt(raw.encode()).decode()


def _decrypt_password(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise SubmitError("Stored mailbox password cannot be read; save the mailbox again.") from exc


def send_email(app: Application) -> dict:
    box = MailboxConfig.objects.filter(user=app.user).first()
    if box is None:
        raise SubmitError("Connect your mailbox first.")
    if not app.to_email:
        raise SubmitError("No recipient email for this application.")
    connection = get_connection(backend=settings.APPLICATION_EMAIL_BACKEND, host=box.host, port=box.port,
                                username=box.username, password=_decrypt_password(box.password_encrypted),
                                use_tls=box.use_tls, timeout=20)
    msg = EmailMessage(subject=f"Application: {app.posting.title}", body=app.kit.cover_letter,
                       from_email=box.from_email, to=[app.to_email], reply_to=[box.from_email],
                       connection=connection)
    msg.attach("resume.txt", app.kit.resume_text, "text/plain")
    try:
        msg.send()
    except Exception as exc:  # smtplib raises many types; none should leak a stack trace to the API
        log.warning("email apply failed: %s", type(exc).__name__)
        raise SubmitError(f"Your mailbox refused the message: {type(exc).__name__}") from exc
    return {"sent_to": app.to_email, "from": box.from_email}


# ---- submit -----------------------------------------------------------------------

def _run_method(app: Application) -> dict:
    kit = {"resume_text": app.kit.resume_text, "cover_letter": app.kit.cover_letter, "answers": app.kit.answers}
    if app.method == Application.Method.ATS:
        profile = getattr(app.user, "profile", None)
        name = (profile.full_name if profile and profile.full_name else app.user.email.split("@")[0])
        return get_ats_adapter(app.platform).submit(app.posting.url, {"name": name, "email": app.user.email}, kit)
    return send_email(app)


def notify_captcha(app: Application) -> None:
    Notification.objects.create(
        user=app.user, kind="captcha", application=app,
        message=f"CAPTCHA on {app.posting.company} ({app.posting.title}). Manual review required.")


def submit(app: Application, confirmed: bool) -> Application:
    user = app.user
    if user.automation_paused:
        raise Blocked("Automation is paused.", 409)
    if app.method == Application.Method.MANUAL:
        raise Blocked("Open the posting and use mark-applied for LinkedIn and Naukri.", 400)
    if app.status in (Application.Status.SUBMITTED, Application.Status.APPLIED):
        raise Blocked("This application was already submitted.", 409)
    if requires_confirmation(user, app.platform) and not confirmed:
        raise Blocked("Review and confirm this application before it is submitted.", 428)
    with transaction.atomic():
        user.__class__.objects.select_for_update().get(pk=user.pk)  # serialise per user so the limit holds
        check_limit(user, app.platform)
        try:
            app.result = _run_method(app)
        except CaptchaDetected as exc:
            record_attempt(app, ApplicationAttempt.Status.CAPTCHA, str(exc))
            app.status = Application.Status.MANUAL_REVIEW
            app.save()
            notify_captcha(app)
            return app
        except SubmitError as exc:
            record_attempt(app, ApplicationAttempt.Status.FAILURE, str(exc))
            app.status = Application.Status.FAILED
            app.result = {"error": str(exc)}
            app.save()
            return app
        record_attempt(app, ApplicationAttempt.Status.SUCCESS)
        app.status = Application.Status.SUBMITTED
        app.save()
        _mark_feed_applied(app)
    return app


def mark_applied(app: Application) -> Application:
    if app.status == Application.Status.APPLIED:
        return app
    check_limit(app.user, app.platform)
    with transaction.atomic():
        record_attempt(app, ApplicationAttempt.Status.SUCCESS, "Marked as applied by the user.")
        app.status = Application.Status.APPLIED
        app.save()
        _mark_feed_applied(app)
    return app
