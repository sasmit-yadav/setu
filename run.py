#!/usr/bin/env python
"""run.py — SETU task runner.

This is Part 37's Makefile, rewritten to run natively on Windows. `make` and
`psql` are not present on the team's machines and installing them (or migrating
to WSL2) costs an hour nobody has; every psql invocation here runs INSIDE the
db container instead, so Docker is the only external dependency.

    python run.py                 list every task
    python run.py db-up           start Postgres+PostGIS, Redis, MailHog
    python run.py db-migrate      alembic upgrade head, against the DIRECT url
    python run.py seed            apply every data/seeds/*.sql in order
    python run.py doctor          report what this machine can and cannot run
    python run.py check           everything CI runs
    python run.py demo            THE GATE (Part 19) — snapshot, offline

Task names match Part 37's Makefile targets exactly, so the spec still reads
true: wherever it says `make seed`, run `python run.py seed`.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).parent.resolve()
VENV_PY = ROOT / ".venv" / ("Scripts" if os.name == "nt" else "bin") / (
    "python.exe" if os.name == "nt" else "python"
)
PY = str(VENV_PY) if VENV_PY.exists() else sys.executable
COMPOSE = ["docker", "compose", "-f", str(ROOT / "infra" / "docker-compose.yml")]

TASKS: dict[str, str] = {}


def task(help_text: str):
    def deco(fn):
        TASKS[fn.__name__.replace("_", "-")] = help_text
        return fn

    return deco


def sh(cmd: list[str], **kw) -> int:
    """Run a command, streaming output. Returns its exit code."""
    print(f"  $ {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=ROOT, **kw)


def must(cmd: list[str], **kw) -> None:
    """Run a command; abort the whole task run if it fails."""
    if sh(cmd, **kw) != 0:
        print(f"\nFAILED: {' '.join(cmd)}", file=sys.stderr)
        sys.exit(1)


def load_env() -> None:
    """Read .env into os.environ. No dependency on python-dotenv being installed
    yet, because db-up must work before pip install has finished."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def psql(sql: str, *, db_url_env: str = "DATABASE_URL_DIRECT") -> int:
    """Run SQL inside the db container — this is why psql is not needed on PATH."""
    return sh(
        [*COMPOSE, "exec", "-T", "db", "psql", "-U", "setu", "-d", "setu",
         "-v", "ON_ERROR_STOP=1", "-c", sql]
    )


# ─────────────────────────────── setup ───────────────────────────────

@task("Create .env from the template if it does not exist")
def setup() -> None:
    env, example = ROOT / ".env", ROOT / ".env.example"
    if env.exists():
        print("  .env already exists — leaving it alone")
    else:
        shutil.copy(example, env)
        print("  .env created from .env.example")
    print("\n  Next:  python run.py secrets   (then paste the values into .env)")


@task("Generate PHONE_HASH_PEPPER, the Ed25519 pair, and the JWT/HMAC secrets")
def secrets() -> None:
    must([PY, "scripts/gen_secrets.py"])


# ─────────────────────────────── database ───────────────────────────────

@task("Start Postgres+PostGIS, Redis, MailHog")
def db_up() -> None:
    must([*COMPOSE, "up", "-d"])
    must([PY, "scripts/wait_for_db.py"])
    print("\n  Postgres :5433 · Redis :6379 · MailHog UI http://localhost:8025")


@task("Stop the local stack (keeps data)")
def db_down() -> None:
    must([*COMPOSE, "down"])


@task("Apply migrations 0001 -> head, against the DIRECT url (Part 23)")
def db_migrate() -> None:
    load_env()
    if not os.environ.get("DATABASE_URL_DIRECT"):
        print("DATABASE_URL_DIRECT is not set. Run: python run.py setup", file=sys.stderr)
        sys.exit(1)
    must([PY, "-m", "alembic", "upgrade", "head"])


@task("Prove every down-revision works: head -> 0006 -> head. The Day-4 exit gate")
def db_roundtrip() -> None:
    load_env()
    must([PY, "-m", "alembic", "upgrade", "head"])
    must([PY, "-m", "alembic", "downgrade", "0006"])
    must([PY, "-m", "alembic", "upgrade", "head"])
    print("\n  ✔ Migration round-trip clean. This is the Day-4 gate.")


@task("DESTROY local data and rebuild. Refuses against any non-localhost url")
def db_reset() -> None:
    load_env()
    must([PY, "scripts/guard_local_only.py"])
    must([*COMPOSE, "down", "-v"])
    db_up()
    db_migrate()
    seed()


@task("Apply every data/seeds/*.sql in lexical order (Rule 3)")
def seed() -> None:
    load_env()
    seeds = sorted((ROOT / "data" / "seeds").glob("*.sql"))
    if not seeds:
        print("  no seed files yet in data/seeds/")
        return
    for f in seeds:
        print(f"  -> {f.name}")
        with f.open("rb") as fh:
            if sh([*COMPOSE, "exec", "-T", "db", "psql", "-U", "setu", "-d", "setu",
                   "-v", "ON_ERROR_STOP=1"], stdin=fh) != 0:
                print(f"\nFAILED applying {f.name}", file=sys.stderr)
                sys.exit(1)
    must([PY, "scripts/verify_seeds.py"])


# ─────────────────────────────── quality ───────────────────────────────

@task("Report exactly what this machine can and cannot run")
def doctor() -> None:
    load_env()
    sh([PY, "scripts/doctor.py"])


@task("Everything CI runs")
def check() -> None:
    load_env()
    must([PY, "-m", "ruff", "check", "services/"])
    must([PY, "-m", "pytest", "tests/unit", "--cov=services/delivery",
          "--cov-fail-under=95"])
    must([PY, "-m", "pytest", "tests/property", "tests/contract", "tests/integration"])
    must([PY, "scripts/check_no_hardcoding.py"])
    must([PY, "scripts/check_env_example.py"])
    must([PY, "scripts/check_channel_capability.py"])


@task("Run the test suite")
def test() -> None:
    must([PY, "-m", "pytest", "-q"])


# ─────────────────────────────── main ───────────────────────────────

def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__.split("    python run.py")[0].strip())
        print("\nTasks:")
        width = max(len(t) for t in TASKS)
        for name, help_text in TASKS.items():
            print(f"  {name:<{width}}  {help_text}")
        return 0
    name = sys.argv[1]
    fn = globals().get(name.replace("-", "_"))
    if name not in TASKS or fn is None:
        print(f"Unknown task '{name}'. Run `python run.py` to list tasks.", file=sys.stderr)
        return 1
    fn()
    return 0


if __name__ == "__main__":
    sys.exit(main())
