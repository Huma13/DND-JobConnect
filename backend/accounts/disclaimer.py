"""Issue #4 (SRS section 7, legal requirement): the disclaimer users accept before automation.

Change DISCLAIMER_VERSION whenever the text changes, so everyone has to accept it again.
"""

DISCLAIMER_VERSION = "1.0"

DISCLAIMER_TEXT = (
    "HAND-JobConnect submits job applications and sends outreach messages using your own "
    "platform credentials and with your consent. You are responsible for what is sent from "
    "your accounts. Team HAND and PES University are not liable for any action a platform "
    "takes on your account (for example a suspension) if you go beyond the recommended "
    "daily usage limits."
)


def has_accepted(user) -> bool:
    """True if the user has accepted the current version of the disclaimer."""
    return user.disclaimer_accepted_at is not None and user.disclaimer_version == DISCLAIMER_VERSION
