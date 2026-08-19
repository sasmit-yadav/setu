from __future__ import annotations

from urllib.parse import urljoin

from fastapi import Request
from twilio.request_validator import RequestValidator

from services.api.settings import settings


def twilio_auth_token() -> str:
    return settings.twilio_webhook_auth_token or settings.twilio_auth_token


async def verify_twilio_form(request: Request) -> dict[str, str]:
    token = twilio_auth_token()
    if not token:
        raise ValueError("twilio_not_configured")
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    validator = RequestValidator(token)
    if not validator.validate(url, params, signature):
        raise PermissionError("invalid_twilio_signature")
    return params


def public_webhook_url(path: str) -> str:
    return urljoin(settings.public_base_url.rstrip("/") + "/", path.lstrip("/"))
