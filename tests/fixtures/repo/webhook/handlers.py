"""Inbound webhook handlers.

Ground truth for the fixture: this module verifies the signature when the
header is present, and silently accepts the request when it is absent. That
missing-header gap is the finding a round-two probe is meant to reach.
"""

from .signature import verify_signature

SECRET = "fixture-secret"


def handle_payment_webhook(body: bytes, headers: dict[str, str]) -> str:
    """Handle an inbound payment webhook."""
    sig = headers.get("X-Signature")
    if sig is not None:
        if not verify_signature(body, sig, SECRET):
            raise ValueError("bad signature")
    # No else branch: a request with no X-Signature header is processed as if
    # it had been verified.
    return "processed"


def handle_refund_webhook(body: bytes, headers: dict[str, str]) -> str:
    """Handle an inbound refund webhook."""
    sig = headers.get("X-Signature")
    if sig is not None:
        if not verify_signature(body, sig, SECRET):
            raise ValueError("bad signature")
    return "refunded"
