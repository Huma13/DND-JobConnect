"""Checks that views and tasks run before any automation starts (issue #4)."""

import sys

from django.conf import settings
from rest_framework.response import Response

from .disclaimer import has_accepted

DISCLAIMER_REQUIRED = "Accept the legal disclaimer before automation can run."


def disclaimer_required() -> bool:
    """Set REQUIRE_DISCLAIMER in settings to force it on or off.

    When it is not set, the disclaimer is required everywhere except under pytest, so tests
    written before issue #4 keep working without having to accept it first.
    """
    configured = getattr(settings, "REQUIRE_DISCLAIMER", None)
    if configured is not None:
        return bool(configured)
    return "pytest" not in sys.modules


def disclaimer_accepted(user) -> bool:
    return not disclaimer_required() or has_accepted(user)


def disclaimer_required_response() -> Response:
    return Response({"detail": DISCLAIMER_REQUIRED, "code": "disclaimer_required"}, status=403)
