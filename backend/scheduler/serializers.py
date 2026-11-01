from rest_framework import serializers

from .models import Schedule, ScheduledRun


class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = ["cadence", "run_time", "weekday", "timezone", "enabled"]

    def validate_timezone(self, value):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise serializers.ValidationError("Unknown time zone.") from exc
        return value

    def validate(self, data):
        cadence = data.get("cadence", getattr(self.instance, "cadence", "daily"))
        weekday = data.get("weekday", getattr(self.instance, "weekday", None))
        if cadence == Schedule.Cadence.WEEKLY and weekday is None:
            raise serializers.ValidationError({"weekday": "Required for a weekly schedule (0 = Monday)."})
        if weekday is not None and not 0 <= weekday <= 6:
            raise serializers.ValidationError({"weekday": "Must be 0 (Monday) to 6 (Sunday)."})
        if cadence == Schedule.Cadence.DAILY:
            data["weekday"] = None
        return data


class ScheduledRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduledRun
        fields = ["id", "trigger", "status", "platforms", "postings_found", "new_matches",
                  "duplicates_hidden", "applications_submitted", "errors", "deferred",
                  "started_at", "finished_at"]
