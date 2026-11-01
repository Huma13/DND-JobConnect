from django.contrib import admin

from .models import Application, ApplicationAttempt, ApplySetting, Notification

admin.site.register([Application, ApplicationAttempt, ApplySetting, Notification])
