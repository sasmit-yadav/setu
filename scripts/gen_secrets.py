#!/usr/bin/env python
"""scripts/gen_secrets.py — generate every secret SETU creates itself (Part 25).

Run ONCE. Paste the output into .env, and share with the team through a vault —
never through chat, never through a commit.

Two of these do NOT behave like API keys, and Part 25 says so for a reason:

  PHONE_HASH_PEPPER      A DATA-SHAPING secret. Every recipient.phone_hash is an
                         HMAC under this pepper. Rotating it invalidates all of
                         them and silently breaks dedupe, enrollment and STOP
                         lookups. Rotating it is a MIGRATION WITH A FULL
                         RECOMPUTE, not an env change. Never rotate mid-build.

  ALERT_SIGNING_SEED_B64 A CLIENT-COUPLED secret. The matching public key is
                         baked into the citizen PWA bundle, so rotating the seed
                         requires shipping a new bundle. Rotating it is a
                         RELEASE, not an env change.

  PGCRYPTO_SYM_KEY       A DATA-SHAPING secret, same category as the pepper.
                         Every recipient.phone_enc / email_enc is
                         pgp_sym_encrypt()'d under this passphrase. Rotating it
                         orphans every already-encrypted value — decrypt-then-
                         re-encrypt every row first, or every phone/email on
                         file becomes permanently unreadable.

The public key is printed too — it is public BY DESIGN (§1.5.3, Rule 11) and is
safe to commit to the build config. A device with no network still verifies
alert authenticity against it, which is the entire point of B10.
"""

from __future__ import annotations

import base64
import secrets
import sys


def _fix_windows_console_encoding() -> None:
    """cmd.exe/PowerShell default to cp1252, which chokes on the box-drawing
    characters below. UTF-8 output is not optional on a mixed-OS six-person
    team, so force it rather than deleting the characters."""
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8")
            except (AttributeError, ValueError):
                pass


def main() -> int:
    _fix_windows_console_encoding()
    print("\n# ── paste into .env ─────────────────────────────────────────────")
    print(f"PHONE_HASH_PEPPER={secrets.token_urlsafe(32)}")
    print(f"PGCRYPTO_SYM_KEY={secrets.token_urlsafe(32)}")
    print(f"JWT_SIGNING_SECRET={secrets.token_urlsafe(48)}")
    print(f"WEBHOOK_HMAC_SECRET={secrets.token_urlsafe(48)}")
    print(f"INTERNAL_ML_KEY={secrets.token_urlsafe(32)}")

    try:
        from nacl.signing import SigningKey
    except ImportError:
        print(
            "\n# ⚠ PyNaCl not installed yet — the Ed25519 signing pair was NOT"
            "\n#   generated. Install requirements.txt, then re-run this script."
            "\n#   B10 peer relay cannot sign without it (Rule 11).",
            file=sys.stderr,
        )
        return 0

    sk = SigningKey.generate()
    seed_b64 = base64.b64encode(bytes(sk)).decode()
    pub_b64 = base64.b64encode(bytes(sk.verify_key)).decode()

    print(f"ALERT_SIGNING_SEED_B64={seed_b64}")
    print("\n# ── paste into web/citizen/.env (PUBLIC by design, §1.5.3) ──────")
    print(f"VITE_ALERT_SIGNING_PUBKEY_B64={pub_b64}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
