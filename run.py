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
ML_VENV_PY = ROOT / ".venv-ml" / ("Scripts" if os.name == "nt" else "bin") / (
    "python.exe" if os.name == "nt" else "python"
)
COMPOSE = ["docker", "compose", "-f", str(ROOT / "infra" / "docker-compose.yml")]
LOCAL_ML_URL = "http://127.0.0.1:8001"
DEFAULT_TRANSLATE_HF_ID = "ai4bharat/indictrans2-en-indic-dist-200M"

TASKS: dict[str, str] = {}


def task(help_text: str):
    def deco(fn):
        TASKS[fn.__name__.replace("_", "-")] = help_text
        return fn

    return deco


def sh(cmd: list[str], *, cwd: pathlib.Path | None = None, **kw) -> int:
    """Run a command, streaming output. Returns its exit code."""
    print(f"  $ {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=cwd or ROOT, **kw)


def must(cmd: list[str], *, cwd: pathlib.Path | None = None, **kw) -> None:
    """Run a command; abort the whole task run if it fails."""
    if sh(cmd, cwd=cwd, **kw) != 0:
        print(f"\nFAILED: {' '.join(cmd)}", file=sys.stderr)
        sys.exit(1)


def _parse_env_file(path: pathlib.Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def _ml_url_for_laptop(raw: str) -> str:
    """Laptop worker / translate-cloud: use local :8001 unless a real Space URL is set."""
    value = (raw or "").strip()
    lowered = value.lower()
    if not value:
        return LOCAL_ML_URL
    if "your-space" in lowered or "placeholder" in lowered or "example.com" in lowered:
        return LOCAL_ML_URL
    return value


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
    must([PY, "scripts/check_no_torch.py"])
    must([PY, "scripts/check_env_example.py"])
    must([PY, "scripts/check_channel_capability.py"])
    must([PY, "scripts/check_pwa_config.py"])


@task("Run the test suite")
def test() -> None:
    must([PY, "-m", "pytest", "-q"])


@task("Start FastAPI on :8000")
def api() -> None:
    load_env()
    must([PY, "-m", "uvicorn", "services.api.main:app", "--reload", "--port", "8000"])


@task("API on :8000 against the DEPLOYED Neon + Upstash (.env.cloud)")
def api_cloud() -> None:
    """Same data plane as worker-cloud. Use this when Send must run the
    laptop's current code (SMS-on-moderate, etc.) instead of the stale
    Render box."""
    cloud = ROOT / ".env.cloud"
    if not cloud.exists():
        print("Missing .env.cloud — refusing to fall back to .env.", file=sys.stderr)
        sys.exit(1)
    env = os.environ.copy()
    env.update(_parse_env_file(cloud))
    env["HF_SPACE_URL"] = _ml_url_for_laptop(env.get("HF_SPACE_URL", ""))
    target = env.get("DATABASE_URL_DIRECT", "").split("@")[-1].split("/")[0]
    print(f"api -> db {target} | :8000")
    must(
        [PY, "-m", "uvicorn", "services.api.main:app", "--reload", "--port", "8000"],
        env=env,
    )


@task("Delivery worker (Redis Streams consumer)")
def worker() -> None:
    load_env()
    must([PY, "-m", "services.delivery.worker"])


@task("Delivery worker against the DEPLOYED Neon + Upstash (.env.cloud)")
def worker_cloud() -> None:
    """Run the worker locally but against the cloud data plane.

    Render's free tier has no background workers, so setu-worker is suspended
    there. That is survivable because the worker is not a server: nothing calls
    it, and it needs only Postgres and Redis, both of which are cloud-hosted.
    Running it here makes it a real consumer of the deployed stream.

    Deliberately does NOT fall back to .env if .env.cloud is missing. Silently
    running against local Docker while the operator believes they are draining
    the production queue is the worst possible outcome of a typo — the deployed
    dispatch would sit in Upstash forever with nothing consuming it.
    """
    cloud = ROOT / ".env.cloud"
    if not cloud.exists():
        print(
            "Missing .env.cloud — it holds the Neon + Upstash URLs and the\n"
            "channel credentials for a local worker against the deployed data\n"
            "plane. See docs/DEPLOY.md. Refusing to fall back to .env, because\n"
            "that would drain the LOCAL queue while looking like production.",
            file=sys.stderr,
        )
        sys.exit(1)
    env = os.environ.copy()
    env.update(_parse_env_file(cloud))
    env["HF_SPACE_URL"] = _ml_url_for_laptop(env.get("HF_SPACE_URL", ""))
    target = env.get("DATABASE_URL_DIRECT", "").split("@")[-1].split("/")[0]
    fcm_path = env.get("FCM_SERVICE_ACCOUNT_JSON", "./secrets/fcm-service-account.json")
    fcm_ok = pathlib.Path(fcm_path).is_file() or (
        fcm_path.strip().startswith("{") and "private_key" in fcm_path
    )
    print(f"worker -> db {target} | redis {env.get('REDIS_URL','').split('@')[-1]}")
    print(f"  fcm credentials: {'present' if fcm_ok else 'MISSING — push will fall to SIM'}")
    print(f"  translate: {env['HF_SPACE_URL']}  (start `python run.py ml-load` in another terminal)")
    must([PY, "-m", "services.delivery.worker"], env=env)


@task("Ingestion scheduler (USGS + GDACS pollers)")
def ingest() -> None:
    load_env()
    must([PY, "-m", "services.ingestion.scheduler"])


@task("Apply data/seeds/04_app_config.sql idempotently (ON CONFLICT upsert)")
def seed_config() -> None:
    must([PY, "scripts/upsert_app_config.py"])


@task("Start citizen PWA dev server on :5174")
def citizen_dev() -> None:
    citizen_dir = ROOT / "web" / "citizen"
    if not (citizen_dir / "node_modules").exists():
        must(["npm", "install"], cwd=citizen_dir)
    env = os.environ.copy()
    # Unset baked-in Render URLs. Empty VITE_API_BASE uses the Vite /api proxy
    # to :8000, so a phone on a tunnel still talks to this laptop's API.
    env["VITE_API_BASE"] = env.get("VITE_API_BASE", "")
    print("citizen -> API proxy /api -> http://127.0.0.1:8000 | :5174")
    must(
        ["npm", "run", "dev", "--", "--host", "--port", "5174"],
        cwd=citizen_dir,
        env=env,
    )


@task("Re-run geometry loaders against Neon (.env.neon)")
def neon_geometry() -> None:
    must([PY, "scripts/push_geometry_to_neon.py"])


@task("Full Neon data bootstrap: migrate + config + geometry + verify")
def neon_bootstrap() -> None:
    must([PY, "scripts/bootstrap_neon.py"])


@task("Local data bootstrap: migrate + config + enrollment CSV + verify")
def data_bootstrap() -> None:
    must([PY, "scripts/bootstrap_local_data.py"])


@task("Import data/enrollment/*.csv (dry-run then live)")
def import_enrollment() -> None:
    load_env()
    must([PY, "scripts/import_enrollment_csv.py"])


@task("Assign demo unit_scope_id by geometry name; optional SETU_DEMO_PASSWORD")
def provision_demo() -> None:
    load_env()
    must([PY, "scripts/provision_demo_accounts.py"])


@task("Upsert app_config against .env.neon")
def neon_seed_config() -> None:
    neon = ROOT / ".env.neon"
    if not neon.exists():
        print("Missing .env.neon — copy Neon URLs there first", file=sys.stderr)
        sys.exit(1)
    env = os.environ.copy()
    env["SETU_ENV_FILE"] = str(neon)
    must([PY, "scripts/upsert_app_config.py"], env=env)


@task("Start isolated ML service on :8001 (torch never loads in the API process)")
def ml() -> None:
    load_env()
    must([PY, "-m", "uvicorn", "services.ml.server:app", "--reload", "--port", "8001"])


@task("Start isolated ML on :8001 WITH IndicTrans2 weights (SETU_LOAD_ML_MODELS=1)")
def ml_load() -> None:
    """Same process as `ml`, but actually loads the 200M card.

    Needed for a real Malayalam / Marathi cache. First start downloads the
    gated weights — accept the model terms on Hugging Face and set HF_TOKEN
    if the hub returns 401. Leave this terminal open next to worker-cloud.
    No --reload: restarting mid-load would re-download.

    Prefers `.venv-ml` so torch never lands in the API venv. Create it with:
      python -m venv .venv-ml
      .venv-ml\\Scripts\\python -m pip install -r services/ml/requirements-ml.txt
    """
    load_env()
    ml_py = str(ML_VENV_PY) if ML_VENV_PY.exists() else PY
    if not ML_VENV_PY.exists():
        print(
            "  .venv-ml missing — using the API venv. Prefer a separate env:\n"
            "    python -m venv .venv-ml\n"
            "    .venv-ml\\Scripts\\python -m pip install -r services/ml/requirements-ml.txt"
        )
    env = os.environ.copy()
    cloud = ROOT / ".env.cloud"
    if cloud.exists():
        cloud_env = _parse_env_file(cloud)
        # Same key the worker will send. A mismatch is a silent 401 on /translate.
        if cloud_env.get("INTERNAL_ML_KEY"):
            env["INTERNAL_ML_KEY"] = cloud_env["INTERNAL_ML_KEY"]
    env["SETU_LOAD_ML_MODELS"] = "1"
    env.setdefault("SETU_TRANSLATE_HF_ID", DEFAULT_TRANSLATE_HF_ID)
    if not env.get("HF_TOKEN") and not env.get("HUGGING_FACE_HUB_TOKEN"):
        print(
            "  no HF_TOKEN in the environment — if the hub 401s, accept the "
            "IndicTrans2 terms and set HF_TOKEN (never commit it)"
        )
    must(
        [ml_py, "-m", "uvicorn", "services.ml.server:app", "--port", "8001"],
        env=env,
    )


@task("Fill missing alert_translation rows on Neon via local ML (.env.cloud)")
def translate_cloud() -> None:
    """Render cannot reach laptop :8001. After Save draft, run this so
    Validate sees Malayalam before Send (Kerala severe requires it)."""
    cloud = ROOT / ".env.cloud"
    if not cloud.exists():
        print("Missing .env.cloud — refusing to fall back to .env.", file=sys.stderr)
        sys.exit(1)
    env = os.environ.copy()
    env.update(_parse_env_file(cloud))
    env["HF_SPACE_URL"] = _ml_url_for_laptop(env.get("HF_SPACE_URL", ""))
    print(f"  translate-cloud -> {env['HF_SPACE_URL']}")
    must([PY, "scripts/translate_pending.py"], env=env)


@task("Verify admin units, config, channels, recipients")
def verify_data() -> None:
    load_env()
    must([PY, "scripts/verify_data_layer.py"])


@task("Write data/snapshots/<date>.json from the local database")
def snapshot() -> None:
    load_env()
    must([PY, "scripts/snapshot.py"])


@task("Download a local Protomaps extract (or write the placeholder if extract fails)")
def fetch_basemap() -> None:
    must([PY, "scripts/fetch_basemap.py"])


@task("THE GATE (Part 19) — load the frozen snapshot and prove it is not empty")
def demo() -> None:
    load_env()
    must([PY, "scripts/guard_local_only.py"])
    db_up()
    db_migrate()
    snapshot_dir = ROOT / "data" / "snapshots"
    latest = sorted(snapshot_dir.glob("*.json"))
    if not latest:
        seed_config()
        print("  no snapshot yet — seeding a local demo board, then capturing one")
        must([PY, "scripts/seed_demo_board.py"])
        must([PY, "scripts/eval_models.py"])
        must([PY, "scripts/snapshot.py"])
        latest = sorted(snapshot_dir.glob("*.json"))
    if not latest:
        print("FAILED: still no snapshot in data/snapshots", file=sys.stderr)
        sys.exit(1)
    must([PY, "scripts/load_snapshot.py", "--latest"])
    must([PY, "scripts/verify_snapshot.py", "--latest", "--strict"])
    seed_config()
    must([PY, "scripts/provision_demo_accounts.py"])
    print()
    print("  Snapshot loaded. Console :5173 · Citizen :5174 · API :8000")
    print("  Citizen/officer login needs SETU_DEMO_PASSWORD then python run.py provision-demo")
    print("  Isolated ML (optional): python run.py ml")
    print("  No network calls required from here. Unplug the cable and re-check.")
    print()
    procfile = ROOT / "infra" / "Procfile.demo"
    honcho = shutil.which("honcho")
    if honcho and procfile.exists():
        must([honcho, "-f", str(procfile), "start"])
        return
    print("  honcho not on PATH. Start in three terminals:")
    print("    python run.py api")
    print("    python run.py worker")
    print("    cd web/console && npm run dev -- --port 5173")
    print("    cd web/citizen && npm run dev -- --port 5174")


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
