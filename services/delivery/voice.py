"""ISO 639-1 -> Twilio `<Say language=...>` tags.

A bare `<Say>` is spoken by Twilio's default en-US voice. Feeding it
Devanagari or Malayalam produces garbage or silence, so the IVR must name a
voice that can actually read the script it is handed.

Twilio only ships voices for a subset of Indian languages. This map holds
**only** the tags verified in the Twilio console — a language absent here is
not a language Twilio can speak, and `voice_tag()` returns None so the caller
falls back to the alert's source text in English rather than pretending the
call said something it did not. Add an entry only after hearing it work.
"""

from __future__ import annotations

ENGLISH_TAG = "en-IN"

# Verified in the Twilio TTS voice list. Hindi is Polly `Aditi` (hi-IN).
# Malayalam and Marathi have no Twilio voice at the time of writing — do not
# add them here on the assumption that they do.
SAY_LANGUAGES: dict[str, str] = {
    "en": ENGLISH_TAG,
    "hi": "hi-IN",
}


def voice_tag(iso: str | None) -> str | None:
    """Twilio language tag for an ISO code, or None if Twilio cannot speak it."""
    if not iso:
        return None
    return SAY_LANGUAGES.get(iso.strip().lower())
