from __future__ import annotations

import hashlib
import hmac

from services.api.settings import settings


def phone_hash(phone_e164: str) -> bytes:
    if not settings.phone_hash_pepper:
        raise RuntimeError("phone_hash_pepper_not_configured")
    normalized = phone_e164.strip()
    return hmac.new(
        settings.phone_hash_pepper.encode(),
        normalized.encode(),
        hashlib.sha256,
    ).digest()


async def normalize_phone_e164(
    conn,
    raw: str,
    *,
    default_country_code: str = "+91",
) -> str:
    from services.api import config_repo

    local_digits = await config_repo.get_int(conn, "enrollment.phone_local_digits")
    country_digits = await config_repo.get_int(conn, "enrollment.phone_country_digits")
    digits = "".join(ch for ch in raw.strip() if ch.isdigit())
    if raw.strip().startswith("+"):
        return f"+{digits}"
    if len(digits) == local_digits:
        cc = default_country_code.lstrip("+")
        return f"+{cc}{digits}"
    if digits.startswith("91") and len(digits) == country_digits:
        return f"+{digits}"
    return f"+{digits}"
