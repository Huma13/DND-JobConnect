from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from accounts.gates import disclaimer_accepted, disclaimer_required_response
from applications.services import Blocked
from matching.models import FeedItem

from . import services
from .models import LINKEDIN_NOTE_MAX, OUTREACH_PLATFORMS, OutreachMessage, Recruiter


class RecruiterSerializer(serializers.ModelSerializer):
    best_channel = serializers.CharField(read_only=True)
    posting = serializers.IntegerField(source="posting_id", read_only=True)

    class Meta:
        model = Recruiter
        fields = ["id", "posting", "name", "title", "linkedin_url", "x_handle", "reason", "best_channel"]
        read_only_fields = ["reason"]

    def validate(self, data):
        if not data.get("linkedin_url") and not data.get("x_handle"):
            raise serializers.ValidationError("Give a LinkedIn profile URL or an X handle.")
        return data


class MessageSerializer(serializers.ModelSerializer):
    recruiter_name = serializers.CharField(source="recruiter.name", read_only=True)
    open_url = serializers.SerializerMethodField()

    class Meta:
        model = OutreachMessage
        fields = ["id", "recruiter", "recruiter_name", "platform", "body", "status", "detail", "open_url",
                  "created_at", "sent_at"]
        read_only_fields = ["recruiter", "platform", "status", "detail", "created_at", "sent_at"]

    def get_open_url(self, obj):
        return obj.recruiter.linkedin_url if obj.platform == "linkedin" else None

    def validate_body(self, value):
        if self.instance and self.instance.platform == "linkedin" and len(value) > LINKEDIN_NOTE_MAX:
            raise serializers.ValidationError(f"LinkedIn notes are limited to {LINKEDIN_NOTE_MAX} characters.")
        return value


def _blocked(exc: Blocked) -> Response:
    return Response({"detail": exc.detail}, status=exc.status)


class RecruiterViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """REQ-14: GET ?feed_item=<id> lists suggested recruiters for that posting."""

    serializer_class = RecruiterSerializer
    pagination_class = None

    def _item(self, pk):
        item = FeedItem.objects.select_related("posting").filter(user=self.request.user, pk=pk).first()
        if item is None:
            raise ValidationError({"feed_item": "Unknown feed item."})
        return item

    def list(self, request, *args, **kwargs):
        item = self._item(request.query_params.get("feed_item"))
        return Response(RecruiterSerializer(services.suggest_recruiters(item.posting), many=True).data)

    def perform_create(self, serializer):
        item = self._item(self.request.data.get("feed_item"))
        serializer.save(posting=item.posting, reason="Added by you.")


class MessageViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                     mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = MessageSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return OutreachMessage.objects.filter(user=self.request.user).select_related("recruiter", "user")

    def create(self, request, *args, **kwargs):
        """REQ-15: a personalised draft from the posting and the user's skills."""
        recruiter = Recruiter.objects.filter(pk=request.data.get("recruiter"),
                                             posting__feed_items__user=request.user).first()
        if recruiter is None:
            raise ValidationError({"recruiter": "Unknown recruiter."})
        try:
            platform = services.channel_for(recruiter, request.data.get("platform"))
        except Blocked as exc:
            return _blocked(exc)
        msg = OutreachMessage.objects.create(user=request.user, recruiter=recruiter, platform=platform,
                                             body=services.draft_message(request.user, recruiter, platform))
        return Response(MessageSerializer(msg).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        msg = self.get_object()
        if msg.status == OutreachMessage.Status.SENT:
            return Response({"detail": "A sent message cannot be edited."}, status=status.HTTP_409_CONFLICT)
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        """X: sent through the API."""
        if not disclaimer_accepted(request.user):
            return disclaimer_required_response()
        try:
            msg = services.send_via_api(self.get_object())
        except Blocked as exc:
            return _blocked(exc)
        return Response(MessageSerializer(msg).data)

    @action(detail=True, methods=["post"], url_path="mark-sent")
    def mark_sent(self, request, pk=None):
        """LinkedIn: the user sent the note from the profile the app opened."""
        try:
            msg = services.mark_sent(self.get_object())
        except Blocked as exc:
            return _blocked(exc)
        return Response(MessageSerializer(msg).data)


class OutreachLimitSerializer(serializers.Serializer):
    platform = serializers.ChoiceField(choices=OUTREACH_PLATFORMS)
    daily_limit = serializers.IntegerField(min_value=0, max_value=200)


@api_view(["GET", "PUT"])
def limits_view(request):
    """REQ-16: daily outreach limit per platform, default 15."""
    if request.method == "PUT":
        ser = OutreachLimitSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        row = services.get_setting(request.user, ser.validated_data["platform"])
        row.daily_limit = ser.validated_data["daily_limit"]
        row.save()
    return Response([{"platform": p, "daily_limit": services.get_setting(request.user, p).daily_limit,
                      "sent_today": services.sent_today(request.user, p)} for p in OUTREACH_PLATFORMS])
