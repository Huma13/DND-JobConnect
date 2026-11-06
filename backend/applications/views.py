
import json

from django.db import transaction
from django.http import HttpResponse
from rest_framework import generics, mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from accounts.gates import disclaimer_accepted, disclaimer_required_response
from core.choices import Platform
from integrations.ats import detect_ats
from matching.models import FeedItem
from resume_parser.models import Profile

from . import services
from .credential_crypto import encrypt_credential
from .kit import build_kit, find_contact_email
from .models import (
    APPLY_PLATFORMS,
    Application,
    ApplicationAttempt,
    ApplicationStatusHistory,
    ApplyKit,
    MailboxConfig,
    Notification,
    PlatformCredential,
)
