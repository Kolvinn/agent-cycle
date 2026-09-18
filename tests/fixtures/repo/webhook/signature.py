"""HMAC signature helpers for inbound webhooks."""

import hashlib
import hmac


def compute_signature(payload: bytes, secret: str) -> str:
    """Return the hex HMAC-SHA256 of ``payload``."""
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def verify_signature(payload: bytes, sig: str, secret: str) -> bool:
    """Constant-time compare of a supplied signature against the computed one."""
    expected = compute_signature(payload, secret)
    return hmac.compare_digest(expected, sig)
