from __future__ import annotations

import base64
import json
from typing import Any

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from services.api.settings import settings


def _signing_key() -> SigningKey:
    raw = base64.b64decode(settings.alert_signing_seed_b64)
    return SigningKey(raw)


def public_key_b64() -> str:
    return base64.b64encode(bytes(_signing_key().verify_key)).decode()


def sign_payload(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    signed = _signing_key().sign(body)
    return base64.b64encode(signed.signature).decode()


def verify_payload(payload: dict[str, Any], signature_b64: str) -> bool:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    signature = base64.b64decode(signature_b64)
    key = VerifyKey(bytes(_signing_key().verify_key))
    try:
        key.verify(body, signature)
        return True
    except BadSignatureError:
        return False
