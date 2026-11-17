from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from app.core.config import settings

try:
    from cryptography.fernet import Fernet  # type: ignore

    _HAS_FERNET = True
except ImportError:
    _HAS_FERNET = False


def _derive_32_byte_key(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("utf-8")).digest()


def encrypt_secret(plaintext: str) -> bytes:
    """Encrypts device/router credentials at rest using Fernet (or HMAC-authenticated keystream fallback)."""
    raw_key = _derive_32_byte_key(settings.master_key)
    if _HAS_FERNET:
        fernet = Fernet(base64.urlsafe_b64encode(raw_key))
        return fernet.encrypt(plaintext.encode("utf-8"))

    nonce = secrets.token_bytes(16)
    data = plaintext.encode("utf-8")
    stream = b""
    counter = 0
    while len(stream) < len(data):
        stream += hmac.new(raw_key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest()
        counter += 1
    cipher = bytes(a ^ b for a, b in zip(data, stream[: len(data)]))
    mac = hmac.new(raw_key, b"v1" + nonce + cipher, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(b"v1" + nonce + mac + cipher)


def decrypt_secret(token: bytes) -> str:
    """Decrypts an encrypted credential payload."""
    raw_key = _derive_32_byte_key(settings.master_key)
    if _HAS_FERNET and not token.startswith(b"djE"):
        try:
            fernet = Fernet(base64.urlsafe_b64encode(raw_key))
            return fernet.decrypt(token).decode("utf-8")
        except Exception:
            pass

    raw = base64.urlsafe_b64decode(token)
    if not raw.startswith(b"v1") or len(raw) < 50:
        raise ValueError("Invalid encrypted credential payload")
    nonce = raw[2:18]
    mac = raw[18:50]
    cipher = raw[50:]
    expected_mac = hmac.new(raw_key, b"v1" + nonce + cipher, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected_mac):
        raise ValueError("Credential integrity check failed")
    stream = b""
    counter = 0
    while len(stream) < len(cipher):
        stream += hmac.new(raw_key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest()
        counter += 1
    plain = bytes(a ^ b for a, b in zip(cipher, stream[: len(cipher)]))
    return plain.decode("utf-8")


def create_access_token(subject: str, expires_in_sec: int = 86400) -> str:
    payload = {
        "sub": subject,
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_in_sec,
    }
    body = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).rstrip(b"=")
    sig = hmac.new(_derive_32_byte_key(settings.master_key), body, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=")
    return f"{body.decode('ascii')}.{sig_b64.decode('ascii')}"


def verify_access_token(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 2:
        raise ValueError("Malformed token")
    body_b64, sig_b64 = parts
    expected_sig = hmac.new(
        _derive_32_byte_key(settings.master_key),
        body_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    expected_b64 = base64.urlsafe_b64encode(expected_sig).rstrip(b"=").decode("ascii")
    if not hmac.compare_digest(sig_b64, expected_b64):
        raise ValueError("Invalid token signature")
    pad = "=" * (-len(body_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(body_b64 + pad).decode("utf-8"))
    if payload.get("exp", 0) < int(time.time()):
        raise ValueError("Token expired")
    return payload


def verify_agent_token(provided_token: str | None) -> bool:
    if not provided_token:
        return False
    return hmac.compare_digest(provided_token, settings.agent_token)
