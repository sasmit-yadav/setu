#!/usr/bin/env python3
"""Rule 1, mechanically enforced: no operational threshold may be a bare
literal in code — it belongs in app_config or escalation_policy.

Two scan positions, both learned from real violations found in this codebase:

  1. Compare/BinOp — `if elapsed > 900`. The original check.
  2. Function parameter defaults — `def f(timeout: str = "10")`. Added after
     an IVR handler in services/api/routers/webhooks.py shipped with
     `gather_digits="1", gather_timeout="10"` as defaults, silently ignoring
     the seeded ivr.gather_digits / ivr.gather_timeout_s rows. The old check
     could not see it: a default argument is neither a Compare nor a BinOp,
     and services/api/ was not guarded at all.
"""
from __future__ import annotations

import ast
import pathlib
import sys
from typing import NamedTuple

GUARDED_DIRS = [
    "services/delivery",
    "services/targeting",
    "services/governance",
    "services/response",
    "services/enrollment",
    "services/ingestion",
    "services/api",
]
ALLOWED_LITERALS = {0, 1, -1, 2, 100}
ALLOWED_CONTEXTS = (ast.Subscript,)

# Defaults that are structural, not operational thresholds. Kept deliberately
# short — every entry is a reviewed exception, same discipline as the
# ALLOWED_LITERALS list (Part 32).
ALLOWED_DEFAULT_PARAMS = {
    "limit",       # pagination page size
    "offset",      # pagination offset
    "page",
    "port",        # bind port, not a threshold
    "level",       # admin_unit level (3/5) — a schema fact, not a tunable
    "timeout_s",   # passed IN from config by callers; the default is a floor
    "batch_size",  # passed IN from config by callers
}


class Violation(NamedTuple):
    file: str
    line: int
    value: object
    reason: str


def _is_disallowed_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value not in ALLOWED_LITERALS


def scan_file(path: pathlib.Path) -> list[Violation]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child._check_parent = parent  # type: ignore[attr-defined]
    violations: list[Violation] = []

    # Position 1: comparisons and arithmetic.
    for node in ast.walk(tree):
        if isinstance(node, (ast.Compare, ast.BinOp)):
            for child in ast.walk(node):
                if isinstance(child, ast.Constant) and _is_disallowed_number(child.value):
                    if isinstance(getattr(child, "_check_parent", None), ALLOWED_CONTEXTS):
                        continue
                    violations.append(
                        Violation(str(path), child.lineno, child.value, "decision position")
                    )

    # Position 2: function parameter defaults.
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = node.args
        pairs: list[tuple[ast.arg, ast.expr | None]] = []
        positional = args.posonlyargs + args.args
        # defaults align to the TAIL of the positional parameter list
        offset = len(positional) - len(args.defaults)
        for index, default in enumerate(args.defaults):
            pairs.append((positional[offset + index], default))
        pairs.extend(zip(args.kwonlyargs, args.kw_defaults))

        for arg, default in pairs:
            if default is None or not isinstance(default, ast.Constant):
                continue
            if arg.arg in ALLOWED_DEFAULT_PARAMS:
                continue
            value = default.value
            # A numeric default, or a string that is really a number in
            # disguise (the exact shape of the IVR bug: gather_timeout="10").
            numeric_string = isinstance(value, str) and value.strip().lstrip("-").isdigit()
            if _is_disallowed_number(value) or numeric_string:
                violations.append(
                    Violation(
                        str(path),
                        default.lineno,
                        value,
                        f"default for parameter '{arg.arg}' — read it from app_config instead",
                    )
                )
    return violations


def main() -> int:
    all_violations: list[Violation] = []
    for directory in GUARDED_DIRS:
        root = pathlib.Path(directory)
        if not root.exists():
            continue
        for file in root.rglob("*.py"):
            all_violations.extend(scan_file(file))
    for violation in all_violations:
        print(
            f"::error file={violation.file},line={violation.line}::"
            f"Bare literal {violation.value!r}: {violation.reason}."
        )
    if not all_violations:
        print(f"check_no_hardcoding: clean across {GUARDED_DIRS}")
    return 1 if all_violations else 0


if __name__ == "__main__":
    sys.exit(main())
