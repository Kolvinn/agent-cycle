"""HTTP routes. Deliberately does not verify signatures at all."""

from webhook.handlers import handle_payment_webhook


def post_webhook(body: bytes, headers: dict[str, str]) -> str:
    """Route an inbound webhook straight to its handler."""
    return handle_payment_webhook(body, headers)
