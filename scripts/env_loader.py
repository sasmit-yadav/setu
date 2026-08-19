from __future__ import annotations

import os
from pathlib import Path


def strip_env_value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def load_env_file(path: Path, *, override: bool = False) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = strip_env_value(value)
        if override:
            os.environ[key] = value
        else:
            os.environ.setdefault(key, value)


def direct_dsn() -> str:
    url = os.environ.get("DATABASE_URL_DIRECT", "postgresql://setu:setu@localhost:5433/setu")
    return url.replace("postgresql+asyncpg://", "postgresql://")
