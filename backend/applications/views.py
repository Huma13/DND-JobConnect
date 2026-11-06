import csv

from django.db import transaction
from django.http import HttpResponse
from rest_framework import generics, mixins, serializers, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from integrations.ats import detect_ats
from matching.models import FeedItem
from resume_parser.models import Profile

from . import services
from .kit import build_kit, find_contact_email
from .models import (
    APPLY_PLATFORMS,
    Application,
    ApplicationAttempt,
    ApplicationStatusHistory,
    ApplyKit,
    MailboxConfig,
    Notification,
)


class KitSerializer(serializers.ModelSerializer):
    posting = serializers.IntegerField(source="posting_id", read_only=True)

    class Meta:
        model = ApplyKit
        fields = ["id", "posting", "resume_text", "cover_letter", "answers", "created_at"]
        read_only_fields = ["id", "posting", "created_at"]


class AttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicationAttempt
        fields = ["id", "application", "platform", "status", "detail", "created_at"]


class ApplicationSerializer(serializers.ModelSerializer):
    posting_url = serializers.URLField(source="posting.url", read_only=True)
    title = serializers.CharField(source="posting.title", read_only=True)
    company = serializers.CharField(source="posting.company", read_only=True)
    kit = KitSerializer(read_only=True)
    attempts = AttemptSerializer(many=True, read_only=True)
    requires_confirmation = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = ["id", "method", "platform", "status", "posting_url", "title", "company", "to_email",
                  "result", "kit", "attempts", "requires_confirmation", "created_at", "updated_at"]

    def get_requires_confirmation(self, obj) -> bool:
        return services.requires_confirmation(obj.user, obj.platform)


class NotificationSerializer(serializers.ModelSerializer):
    application = serializers.IntegerField(source="application_id", read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "kind", "message", "application", "read", "created_at"]


def _feed_item(request, pk) -> FeedItem:
    item = FeedItem.objects.select_related("posting").filter(user=request.user, pk=pk).first()
    if item is None:
        raise ValidationError({"feed_item": "Unknown feed item."})
    return item


def _make_kit(user, posting) -> ApplyKit:
    data = build_kit(Profile.objects.filter(user=user).first(), user, posting)
    return ApplyKit.objects.create(user=user, posting=posting, **data)


def _blocked(exc: services.Blocked) -> Response:
    return Response({"detail": exc.detail}, status=exc.status)


class KitViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """REQ-9: build the kit for a posting, then view, edit, copy or download it."""

    serializer_class = KitSerializer

    def get_queryset(self):
        return ApplyKit.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        item = _feed_item(request, request.data.get("feed_item"))
        return Response(KitSerializer(_make_kit(request.user, item.posting)).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"])
    def edit(self, request, pk=None):
        kit = self.get_object()
        ser = KitSerializer(kit, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        kit = self.get_object()
        which = request.query_params.get("part", "all")
        parts = {"resume": kit.resume_text, "cover_letter": kit.cover_letter}
        if which in parts:
            text = parts[which]
        else:
            answers = "\n\n".join(f"{q}\n{a}" for q, a in kit.answers.items())
            text = f"{kit.resume_text}\n---\n\n{kit.cover_letter}\n---\n\n{answers}\n"
        resp = HttpResponse(text, content_type="text/plain; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="apply-kit-{kit.pk}-{which}.txt"'
        return resp


class ApplicationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                         viewsets.GenericViewSet):
    serializer_class = ApplicationSerializer

    def get_queryset(self):
        qs = (Application.objects.filter(user=self.request.user)
              .select_related("posting", "kit", "user").prefetch_related("attempts"))
        if "status" in self.request.query_params:
            qs = qs.filter(status=self.request.query_params["status"])
        return qs

    def create(self, request, *args, **kwargs):
        """Start an application. method=manual opens the posting with the kit (issue #21)."""
        item = _feed_item(request, request.data.get("feed_item"))
        method = request.data.get("method", Application.Method.MANUAL)
        posting, to_email = item.posting, ""
        if method == Application.Method.MANUAL:
            if posting.platform not in ("linkedin", "naukri"):
                raise ValidationError({"method": "Assisted apply is for LinkedIn and Naukri postings."})
            platform = posting.platform
        elif method == Application.Method.ATS:
            platform = detect_ats(posting.url)
            if platform is None:
                raise ValidationError({"method": "This posting is not on Greenhouse or Lever."})
        elif method == Application.Method.EMAIL:
            platform = "email"
            to_email = request.data.get("to_email") or find_contact_email(posting)
            if not to_email:
                raise ValidationError({"to_email": "This posting lists no contact email; provide one."})
            serializers.EmailField().run_validation(to_email)
        else:
            raise ValidationError({"method": "Use manual, ats or email."})
        if method == Application.Method.MANUAL:
            try:
                services.check_limit(request.user, platform)
            except services.Blocked as exc:
                return _blocked(exc)
        kit = _make_kit(request.user, posting)
        app = Application.objects.create(user=request.user, posting=posting, kit=kit, method=method,
                                         platform=platform, to_email=to_email)
        return Response(ApplicationSerializer(app).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def review(self, request, pk=None):
        """Content of the review popup (REQ-10)."""
        app = self.get_object()
        return Response({
            "application": app.pk, "platform": app.platform, "to_email": app.to_email,
            "posting_url": app.posting.url, "resume_text": app.kit.resume_text,
            "cover_letter": app.kit.cover_letter, "answers": app.kit.answers,
            "requires_confirmation": services.requires_confirmation(request.user, app.platform)})

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        app = self.get_object()
        confirmed = request.data.get("confirmed") in (True, "true", "1", 1)
        try:
            app = services.submit(app, confirmed)
        except services.Blocked as exc:
            return _blocked(exc)
        return Response(ApplicationSerializer(app).data)

    @action(detail=True, methods=["post"], url_path="mark-applied")
    def mark_applied(self, request, pk=None):
        """Issue #21: the user applied on the site themselves."""
        app = self.get_object()
        try:
            app = services.mark_applied(app)
        except services.Blocked as exc:
            return _blocked(exc)
        return Response(ApplicationSerializer(app).data)

    @action(detail=True, methods=["patch"], url_path="change-status")
    def change_status(self, request, pk=None):
        """Allow the user to manually update an application's status (Issue #36)."""
        app = self.get_object()
        new_status = request.data.get("status")

        valid_statuses = [choice[0] for choice in Application.Status.choices]

        if new_status not in valid_statuses:
            raise ValidationError({
                "status": f"Invalid status. Choose one of: {', '.join(valid_statuses)}."
            })

        if new_status == app.status:
            return Response(ApplicationSerializer(app).data)

        with transaction.atomic():
            ApplicationStatusHistory.objects.create(
                application=app,
                user=request.user,
                old_status=app.status,
                new_status=new_status,
            )
            app.status = new_status
            app.save(update_fields=["status", "updated_at"])

        return Response(ApplicationSerializer(app).data)

    @action(detail=False, methods=["get"], url_path="export")
    def export_csv(self, request):
        """Export the user's application history as CSV (Issue #38)."""
        applications = self.get_queryset().order_by("-created_at", "-id")

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="application_history.csv"'
        )

        writer = csv.writer(response)
        writer.writerow([
            "Application ID",
            "Job Title",
            "Company",
            "Platform",
            "Method",
            "Status",
            "Recipient Email",
            "Applied Date",
            "Last Updated",
        ])

        for app in applications:
            writer.writerow([
                app.id,
                app.posting.title,
                app.posting.company,
                app.platform,
                app.method,
                app.status,
                app.to_email,
                app.created_at.isoformat(),
                app.updated_at.isoformat(),
            ])

        return response


class AttemptViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """REQ-12: the attempt history."""

    serializer_class = AttemptSerializer

    def get_queryset(self):
        qs = ApplicationAttempt.objects.filter(user=self.request.user)
        if "status" in self.request.query_params:
            qs = qs.filter(status=self.request.query_params["status"])
        return qs


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        Notification.objects.filter(user=request.user, pk=pk).update(read=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class LimitUpdateSerializer(serializers.Serializer):
    platform = serializers.ChoiceField(choices=APPLY_PLATFORMS)
    daily_limit = serializers.IntegerField(min_value=0, max_value=500, required=False)
    full_auto = serializers.BooleanField(required=False)


@api_view(["GET", "PUT"])
def limits_view(request):
    """REQ-10, REQ-11: per-platform daily limit (default 20) and Full-Auto."""
    if request.method == "PUT":
        ser = LimitUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        row = services.get_setting(request.user, ser.validated_data["platform"])
        for field in ("daily_limit", "full_auto"):
            if field in ser.validated_data:
                setattr(row, field, ser.validated_data[field])
        row.save()
    out = []
    for platform in APPLY_PLATFORMS:
        row = services.get_setting(request.user, platform)
        out.append({"platform": platform, "daily_limit": row.daily_limit, "full_auto": row.full_auto,
                    "used_today": services.used_today(request.user, platform)})
    return Response(out)


class MailboxSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = MailboxConfig
        fields = ["host", "port", "username", "password", "from_email", "use_tls"]


class MailboxView(generics.RetrieveUpdateAPIView):
    """The user's own SMTP mailbox for email applications. The password is write-only and stored encrypted."""

    serializer_class = MailboxSerializer

    def get_object(self):
        box = MailboxConfig.objects.filter(user=self.request.user).first()
        if box is None:
            from django.http import Http404
            raise Http404
        return box

    def update(self, request, *args, **kwargs):
        box = MailboxConfig.objects.filter(user=request.user).first()
        ser = MailboxSerializer(box, data=request.data, partial=bool(box and kwargs.get("partial")))
        ser.is_valid(raise_exception=True)
        data = dict(ser.validated_data)
        data["password_encrypted"] = services.encrypt_password(data.pop("password")) if "password" in data \
            else getattr(box, "password_encrypted", "")
        MailboxConfig.objects.update_or_create(user=request.user, defaults=data)
        return Response({k: v for k, v in ser.data.items()})
