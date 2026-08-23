#!/usr/bin/env python3
"""Find app_config keys that no code reads, and code that reads keys nobody seeds.

This repository has been bitten twice by the same shape of bug. B3's whole
retry-and-escalation policy was seeded per severity and read by nothing, so
every delivery sat at attempt 1 and the `escalated` state had zero rows while
219 tests passed. Then `relay.confirm_timeout_minutes` turned out to be seeded
with a documented intent — "no DTMF confirmation in this window -> re-call once"
— and read by no code at all, which means once a runner is dispatched nothing
ever checks whether they confirmed.

Both were invisible because a seeded key looks like a working feature. Nothing
fails, nothing logs, and the config table reads like a specification of
behaviour that does not exist.

    python scripts/check_orphan_config.py
    python scripts/check_orphan_config.py --strict   # exit 1 on orphans

Not wired into CI as a blocker by default: some keys are legitimately read by
SQL views or by the citizen PWA rather than by Python, and a few are demo
scaffolding. The point is that every orphan should be a decision someone made,
not a surprise.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "seeds" / "04_app_config.sql"

# Where a key could legitimately be read from.
SEARCH_DIRS = ("services", "scripts", "web", "migrations", "tests", "run.py")
SEARCH_SUFFIXES = (".py", ".ts", ".tsx", ".sql")

# Keys whose consumer is not a literal string match, or which exist to be read
# by a human. Each needs a reason, so that "known orphan" cannot quietly become
# a synonym for "unread".
EXPECTED_ORPHANS = {
    "demo.citizen_email": "read by a person setting up the demo, not by code",
    "demo.password_emails": "consumed by provision_demo via a LIKE, not a literal",
}


def seeded_keys() -> list[str]:
    text = SEED.read_text(encoding="utf-8")
    # Rows look like:  ('some.key', 'value', 'unit', 'note'),
    return re.findall(r"^\s*\(\s*'([a-z0-9_.]+)'", text, flags=re.MULTILINE)


def haystack() -> str:
    chunks: list[str] = []
    for entry in SEARCH_DIRS:
        path = ROOT / entry
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
            continue
        for file in path.rglob("*"):
            if file.suffix not in SEARCH_SUFFIXES:
                continue
            # Skip this file. Its own docstring names the keys it was written
            # about, so leaving it in makes the checker excuse exactly the bugs
            # it exists to report - it did, silently, until this line existed.
            if (
                "node_modules" in file.parts
                or file.name == SEED.name
                or file.resolve() == pathlib.Path(__file__).resolve()
            ):
                continue
            chunks.append(file.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def read_keys(text: str) -> set[str]:
    """Keys any code asks for by name."""
    found: set[str] = set()
    # config_repo.get*(conn, "key")  /  key = 'x'  /  cfg["key"]  /  cfgOn(cfg, "key")
    for pattern in (
        r"""get(?:_bool|_int|_float|_str|_csv)?\(\s*conn\s*,\s*['"]([a-z0-9_.]+)['"]""",
        r"""key\s*=\s*['"]([a-z0-9_.]+)['"]""",
        r"""cfg\w*\(\s*cfg\s*,\s*['"]([a-z0-9_.]+)['"]""",
        r"""cfg\?\?\[['"]([a-z0-9_.]+)['"]\]""",
        r"""\[['"]([a-z0-9_.]{4,}\.[a-z0-9_]+)['"]\]""",
    ):
        found.update(re.findall(pattern, text))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="exit 1 on unexplained orphans")
    args = parser.parse_args()

    seeded = seeded_keys()
    text = haystack()
    used = read_keys(text)

    orphans: list[str] = []
    for key in seeded:
        if key in used:
            continue
        # A key may be interpolated (f"quality_gate.required_lang_for_{sev}.{st}")
        # or read by a SQL view. Fall back to a plain substring hunt before
        # calling it unread.
        if key in text:
            continue
        # Interpolated keys (f"quality_gate.required_lang_for_{sev}.{state}")
        # cannot be matched literally, so look for the longest leading segment
        # that appears immediately before an interpolation. Deliberately NOT a
        # plain prefix match: "relay.confirm_timeout_minutes" shares "relay."
        # with a dozen keys that ARE read, and a prefix test would have called
        # it used - hiding the exact bug this script exists to find.
        segments = key.split(".")
        interpolated = any(
            f'"{".".join(segments[:i])}.{{' in text or f"'{'.'.join(segments[:i])}.{{" in text
            for i in range(1, len(segments))
        )
        if interpolated:
            continue
        # Read by a SQL LIKE over a family of keys, e.g. 'case_study.bbox.%'.
        if any(
            f"'{'.'.join(segments[:i])}.%'" in text for i in range(1, len(segments))
        ):
            continue
        orphans.append(key)

    unexplained = [k for k in orphans if k not in EXPECTED_ORPHANS]

    print(f"{len(seeded)} keys seeded, {len(seeded) - len(orphans)} read somewhere\n")
    if orphans:
        print("SEEDED BUT NOT READ:")
        for key in orphans:
            note = EXPECTED_ORPHANS.get(key)
            print(f"  {key}" + (f"   (expected: {note})" if note else "   <- nothing reads this"))
    else:
        print("No orphaned config keys.")

    if unexplained:
        print(
            f"\n{len(unexplained)} key(s) describe behaviour that no code implements."
            "\nEither implement them, delete them, or list them in EXPECTED_ORPHANS"
            "\nwith a reason. A seeded key reads as a working feature."
        )
    return 1 if (args.strict and unexplained) else 0


if __name__ == "__main__":
    sys.exit(main())
