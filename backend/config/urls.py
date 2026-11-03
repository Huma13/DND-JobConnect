from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path


def health(_request):
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "db_unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health),
    path("api/auth/", include("accounts.urls")),
    path("api/jobs/", include("matching.urls")),
    path("api/scheduler/", include("scheduler.urls")),
    path("api/applications/", include("applications.urls")),
    path("api/outreach/", include("outreach.urls")),
    path("api/resume/", include("resume_parser.urls")),
]
