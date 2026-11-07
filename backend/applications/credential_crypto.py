
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings


def _get_encryption_key():
    key = getattr(settings, "PLATFORM_CREDENTIAL_ENCRYPTION_KEY", "")

    if not key:
        raise RuntimeError(
            "Platform credential encryption key is not configured."
        )

    try:
        decoded_key = base64.urlsafe_b64decode(key)
    except Exception as exc:
        raise RuntimeError("Invalid platform credential encryption key.") from exc

    if len(decoded_key) != 32:
        raise RuntimeError(
            "Platform credential encryption key must decode to 32 bytes."
        )

    return decoded_key


def encrypt_credential(plaintext):
    if not isinstance(plaintext, str) or not plaintext:
        raise ValueError("Credential must be a non-empty string.")

    key = _get_encryption_key()
    nonce = os.urandom(12)

    encrypted = AESGCM(key).encrypt(
        nonce,
        plaintext.encode("utf-8"),
        None,
    )

    return base64.urlsafe_b64encode(nonce + encrypted).decode("ascii")


def decrypt_credential(ciphertext):
    if not ciphertext:
        return ""

    key = _get_encryption_key()
    raw = base64.urlsafe_b64decode(ciphertext)

    nonce = raw[:12]
    encrypted = raw[12:]

    return AESGCM(key).decrypt(
        nonce,
        encrypted,
        None,
    ).decode("utf-8")
