"""services/api/settings.py — the ONE place environment variables are read.

Rule 1 says thresholds live in config tables, never as literals in code. Part 38's
documented exception: you cannot read app_config before you have a connection
pool with which to read it, so exactly the values needed to BOOTSTRAP that pool
(and a handful of process-level secrets) come from the environment instead.
Nothing else should call os.environ directly — go through Settings.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── database: two urls, not one (Part 23) ──
    database_url_pooled: str = "postgresql+asyncpg://setu:setu@localhost:5433/setu"
    database_url_direct: str = "postgresql://setu:setu@localhost:5433/setu"
    db_pool_size: int = 10
    db_pool_max_overflow: int = 5
    db_pool_timeout_s: int = 10

    # ── redis (§1.4: local for dev, ALWAYS) ──
    redis_url: str = "redis://localhost:6379/0"
    redis_namespace: str = "setu:v1"

    # ── channels ──
    fcm_service_account_json: str = "./secrets/fcm-service-account.json"
    # Firebase WEB config — not secret (it ships inside the PWA bundle either
    # way), but it's deployment-environment-specific like hf_space_url, so it
    # lives here rather than in app_config (which is business policy, not
    # per-environment identifiers).
    firebase_api_key: str = ""
    firebase_project_id: str = ""
    firebase_messaging_sender_id: str = ""
    firebase_app_id: str = ""
    firebase_vapid_public_key: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_webhook_auth_token: str = ""
    twilio_from_number: str = ""
    brevo_api_key: str = ""

    # ── v3.0 secrets (Part 25 — see the rotation notes in .env.example) ──
    phone_hash_pepper: str = ""
    pgcrypto_sym_key: str = ""
    alert_signing_seed_b64: str = ""

    # ── ml service (Part 22 — services/api must never import torch) ──
    hf_space_url: str = ""
    internal_ml_key: str = ""
    setu_load_ml_models: str = ""
    setu_translate_hf_id: str = ""
    setu_embed_hf_id: str = ""

    # ── platform ──
    jwt_signing_secret: str = ""
    webhook_hmac_secret: str = ""
    sentry_dsn: str = ""
    sentry_enabled: bool = True
    opencellid_token: str = ""
    public_base_url: str = "http://localhost:8000"
    slack_or_discord_alert_webhook: str = ""


settings = Settings()
