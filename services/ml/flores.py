"""ISO 639-1 → FLORES-200 codes for IndicTrans2 en-indic.

The model card will not emit usable Indic text unless both the tokenizer and
IndicTransToolkit see these tags. SETU stores `ml` / `mr` / `hi` on
`recipient.preferred_lang` and `alert.lang`; this module is the only place
those codes become FLORES tags. It must stay importable without torch — the
Space image copies it next to `server.py`, and the API process must never
load weights.
"""

from __future__ import annotations

# Source side of ai4bharat/indictrans2-en-indic-dist-200M.
SOURCE_FLORES = "eng_Latn"

# Target side. Keys are the ISO codes SETU already uses in app_config and
# recipient rows. Values are the FLORES-200 tags the 200M card lists.
EN_INDIC_TARGETS: dict[str, str] = {
    "as": "asm_Beng",
    "bn": "ben_Beng",
    "gu": "guj_Gujr",
    "hi": "hin_Deva",
    "kn": "kan_Knda",
    "ml": "mal_Mlym",
    "mr": "mar_Deva",
    "or": "ory_Orya",
    "pa": "pan_Guru",
    "ta": "tam_Taml",
    "te": "tel_Telu",
    "ur": "urd_Arab",
}


def flores_target(iso: str) -> str | None:
    key = iso.strip().lower()
    if key in {"en", "eng", "eng_latn"}:
        return SOURCE_FLORES
    return EN_INDIC_TARGETS.get(key)


def is_english(iso: str) -> bool:
    return iso.strip().lower() in {"en", "eng", "eng_latn"}
