#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN = [
    ROOT / "services" / "api",
    ROOT / "services" / "delivery",
    ROOT / "services" / "response",
    ROOT / "services" / "governance",
    ROOT / "services" / "audit",
    ROOT / "services" / "targeting",
    ROOT / "services" / "ingestion",
    ROOT / "services" / "enrollment",
]
BANNED = {"torch", "transformers"}


def main() -> int:
    hits: list[str] = []
    for folder in SCAN:
        if not folder.exists():
            continue
        for path in folder.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".", 1)[0]
                        if root in BANNED:
                            hits.append(f"{path.relative_to(ROOT)}: import {alias.name}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    root = node.module.split(".", 1)[0]
                    if root in BANNED:
                        hits.append(f"{path.relative_to(ROOT)}: from {node.module}")
    if hits:
        for hit in hits:
            print(f"FAIL {hit}")
        return 1
    print("check_no_torch: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
