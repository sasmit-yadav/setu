#!/usr/bin/env python3
from __future__ import annotations

import ast
import pathlib
import re
import sys
from typing import NamedTuple

ROOT = pathlib.Path(__file__).resolve().parents[1]
GUARDED_DIRS = [
    "services/delivery",
    "services/targeting",
    "services/governance",
    "services/response",
    "services/enrollment",
    "services/ingestion",
    "services/api",
    "services/ml",
]
SQL_GUARDED = ["data/seeds", "migrations"]
TS_GUARDED_NAMES = {"relay.ts", "verify.ts", "response.ts", "sw.ts"}
ALLOWED_LITERALS = {0, 1, -1, 2, 100}
SQL_ALLOWED = {0, 1, 2, 100, 100.0, 4326}
ALLOWED_CONTEXTS = (ast.Subscript,)
ALLOWED_DEFAULT_PARAMS = {
    "limit",
    "offset",
    "page",
    "port",
    "level",
    "timeout_s",
    "batch_size",
}
SQL_COMPARE = re.compile(
    r"(?:>=|<=|!=|<>|>|<|=)\s*(-?\d+(?:\.\d+)?)",
)
TS_COMPARE = re.compile(
    r"(?:>=|<=|===|!==|==|>|<)\s*(-?\d+(?:\.\d+)?)",
)


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

    for node in ast.walk(tree):
        if isinstance(node, (ast.Compare, ast.BinOp)):
            for child in ast.walk(node):
                if isinstance(child, ast.Constant) and _is_disallowed_number(child.value):
                    if isinstance(getattr(child, "_check_parent", None), ALLOWED_CONTEXTS):
                        continue
                    violations.append(
                        Violation(str(path), child.lineno, child.value, "decision position")
                    )

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = node.args
        pairs: list[tuple[ast.arg, ast.expr | None]] = []
        positional = args.posonlyargs + args.args
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


def _sql_chunks(text: str) -> list[tuple[int, str]]:
    chunks: list[tuple[int, str]] = []
    upper = text.upper()
    needle = "CREATE VIEW"
    start = 0
    while True:
        idx = upper.find(needle, start)
        if idx < 0:
            break
        line = text[:idx].count("\n") + 1
        chunks.append((line, text[idx:]))
        start = idx + len(needle)
    return chunks


def scan_sql(path: pathlib.Path) -> list[Violation]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        bodies = _sql_chunks(text)
        if not bodies:
            return []
    else:
        bodies = [(1, text)] if "CREATE VIEW" in text.upper() else []
    violations: list[Violation] = []
    for base_line, body in bodies:
        view = body
        end = view.upper().find("CREATE VIEW", 1)
        if end > 0:
            view = view[:end]
        if "config-exempt" in view:
            continue
        for match in SQL_COMPARE.finditer(view):
            raw = match.group(1)
            number = float(raw) if "." in raw else int(raw)
            if number in SQL_ALLOWED or number in ALLOWED_LITERALS:
                continue
            line = base_line + view[: match.start()].count("\n")
            violations.append(
                Violation(str(path), line, number, "SQL comparison — move the floor to app_config")
            )
    return violations


def scan_ts(path: pathlib.Path) -> list[Violation]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    violations: list[Violation] = []
    for index, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        for match in TS_COMPARE.finditer(line):
            raw = match.group(1)
            number = float(raw) if "." in raw else int(raw)
            if number in ALLOWED_LITERALS:
                continue
            violations.append(
                Violation(str(path), index, number, "TS comparison — read from public config")
            )
    return violations


def main() -> int:
    all_violations: list[Violation] = []
    for directory in GUARDED_DIRS:
        root = ROOT / directory
        if not root.exists():
            continue
        for file in root.rglob("*.py"):
            all_violations.extend(scan_file(file))
    for directory in SQL_GUARDED:
        root = ROOT / directory
        if not root.exists():
            continue
        for file in root.rglob("*"):
            if file.suffix in {".sql", ".py"}:
                all_violations.extend(scan_sql(file))
    for web_root in (ROOT / "web" / "citizen" / "src", ROOT / "web" / "console" / "src"):
        if not web_root.exists():
            continue
        for file in web_root.rglob("*.ts"):
            if file.name in TS_GUARDED_NAMES:
                all_violations.extend(scan_ts(file))
        for file in web_root.rglob("*.tsx"):
            if file.name in TS_GUARDED_NAMES or file.stem in {"relay", "verify", "response"}:
                all_violations.extend(scan_ts(file))
    for violation in all_violations:
        print(
            f"::error file={violation.file},line={violation.line}::"
            f"Bare literal {violation.value!r}: {violation.reason}."
        )
    if not all_violations:
        print("check_no_hardcoding: clean (python AST, SQL views, TS relay/verify/response/sw)")
    return 1 if all_violations else 0


if __name__ == "__main__":
    sys.exit(main())
