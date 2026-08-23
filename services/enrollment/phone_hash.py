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


# E.164 caps a full international number at 15 digits.
E164_MAX_DIGITS = 15


class PhoneNumberError(ValueError):
    """Raised when a value cannot be a dialable number at all."""


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
        candidate = f"+{digits}"
    elif len(digits) == local_digits:
        cc = default_country_code.lstrip("+")
        candidate = f"+{cc}{digits}"
    elif digits.startswith("91") and len(digits) == country_digits:
        candidate = f"+{digits}"
    else:
        candidate = f"+{digits}"
    # The fall-through above used to be a plain return, so "12345" normalised to
    # "+12345" and enrolled cleanly. An unroutable number is worse than a
    # rejected row: it becomes a consented recipient, it inflates the target
    # count an officer reads before sending, and every delivery to it fails
    # forever. E.164 allows at most 15 digits, and nothing shorter than the
    # national significant number can be dialled.
    body = candidate.lstrip("+")
    if not body.isdigit() or not (local_digits <= len(body) <= E164_MAX_DIGITS):
        raise PhoneNumberError(
            f"{raw.strip()!r} is not a dialable number "
            f"({len(body)} digits; need {local_digits}-{E164_MAX_DIGITS})"
        )
    return candidate
