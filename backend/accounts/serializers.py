from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()

# The username is the email address, so an email must fit the username column.
USERNAME_MAX_LENGTH = User._meta.get_field("username").max_length


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["id", "email", "password"]

    def validate_email(self, value):
        if len(value) > USERNAME_MAX_LENGTH:
            raise serializers.ValidationError(
                f"Email must be at most {USERNAME_MAX_LENGTH} characters."
            )
        # "A@x.com" and "a@x.com" are the same mailbox.
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, data):
        # SRS 6.5: registration only ever creates a Job Seeker. The role is set here on
        # purpose, so it stays safe even if someone later adds fields to this serializer.
        return User.objects.create_user(
            username=data["email"],
            email=data["email"],
            password=data["password"],
            role=User.Role.JOB_SEEKER,
        )
