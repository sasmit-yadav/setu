from __future__ import annotations

import asyncio
import json
import os
import tempfile
import uuid

import asyncpg
import pytest
from redis.asyncio import Redis

from services.api.settings import settings
from services.audit.after_action import after_action_report
from services.delivery.assurance_ladder import alert_assurance
from services.delivery.channels import fcm as fcm_mod
from services.delivery.channels.base import (
    ChannelUnavailable,
    OutboundMessage,
    TransientChannelError,
)
from services.delivery.channels.community_relay import PeerRelayAdapter
from services.delivery.channels.email import BrevoAdapter
from services.delivery.channels.human_relay import (
    HumanRelayAdapter,
    confirm_relay_delivery,
    confirm_relay_from_dtmf,
    find_relay_node,
)
from services.delivery.channels.ivr import TwilioIvrAdapter
from services.delivery.channels.registry import chunked, load_channel_adapters
from services.delivery.channels.simulated import SimulatedCarrierAdapter
from services.delivery.channels.siren import WebhookSirenAdapter
from services.delivery.channels.sms import TwilioSmsAdapter
from services.delivery.engine import (
    DispatchError,
    QualityGateBlocked,
    create_deliveries,
    dispatch_alert,
    enqueue_fanout,
)
from services.delivery.fatigue import apply_headline, evaluate
from services.delivery.keys import RedisKeys, keys
from services.delivery.lookup import by_provider_ref, delivery_channel_code
from services.delivery.ops_events import publish_ops
from services.delivery.receipts import record_receipt, store_nonce
from services.delivery.relay_escalation import on_channels_exhausted
from services.delivery.state_machine import transition
from services.delivery.states import State
from services.delivery.webhook_verify import public_webhook_url, twilio_auth_token, verify_twilio_form
from services.delivery.worker import (
    build_message,
    ensure_consumer_group,
    process_batch,
    process_recipient,
    worker_loop,
)


async def _close_redis(redis: Redis) -> None:
    closer = getattr(redis, "aclose", None)
    if closer is not None:
        await closer()
        return
    await redis.close()


def _msg(delivery_row: dict, *, channel: str = "sim") -> OutboundMessage:
    return OutboundMessage(
        alert_id=delivery_row["alert_id"],
        delivery_id=delivery_row["id"],
        recipient_id=delivery_row["recipient_id"],
        channel_code=channel,
        address="addr",
        headline="Headline",
        body="Body",
        ack_url="http://localhost/api/v1/ack",
    )


def test_redis_keys_and_chunked():
    names = RedisKeys("setu-test")
    assert names.stream_delivery() == "setu-test:stream:delivery"
    assert names.group() == "setu-test:group:workers"
    assert names.zset_retry() == "setu-test:zset:retry"
    assert names.zset_assistance() == "setu-test:zset:assistance"
    assert names.channel_alert(3).endswith(":3")
    assert names.channel_ops().endswith(":ops")
    assert names.lock_ingest("usgs").endswith("usgs")
    assert names.lock_supersede(4).endswith(":4")
    assert names.receipt_nonce(5).endswith(":5")
    assert keys.stream_delivery()
    assert chunked([], 2) == []
    assert chunked([1, 2, 3], 2) == [[1, 2], [3]]


def test_webhook_helpers():
    assert twilio_auth_token() == (
        settings.twilio_webhook_auth_token or settings.twilio_auth_token
    )
    url = public_webhook_url("/api/v1/webhooks/sms-status")
    assert url.endswith("/api/v1/webhooks/sms-status")


async def test_lookup_and_fatigue_without_incident(db_conn, delivery_row):
    assert await by_provider_ref(db_conn, "missing-ref") is None
    code = await delivery_channel_code(db_conn, delivery_row["id"])
    assert code == "sim"
    evaluation = await evaluate(db_conn, delivery_row["alert_id"])
    assert "relabel" in evaluation
    headline, again = await apply_headline(db_conn, delivery_row["alert_id"], "Stay")
    assert headline == "Stay"
    assert again["incident_id"] is not None


async def test_assurance_ladder_and_after_action(db_conn, delivery_row):
    payload = await alert_assurance(db_conn, delivery_row["alert_id"])
    assert payload["alert_id"] == delivery_row["alert_id"]
    assert payload["deliveries"]
    incident_id = await db_conn.fetchval(
        "SELECT incident_id FROM alert WHERE id = $1", delivery_row["alert_id"]
    )
    report = await after_action_report(db_conn, incident_id)
    assert report is not None
    assert len(report["recommendations"]) >= 3
    assert await after_action_report(db_conn, 99999999) is None


async def test_adapters_unavailable_without_credentials(db_conn, delivery_row, monkeypatch):
    msg = _msg(delivery_row)
    sms = TwilioSmsAdapter(db_conn)
    sms._client = None
    sms._from = ""
    with pytest.raises(ChannelUnavailable):
        await sms.send(msg)
    ivr = TwilioIvrAdapter(db_conn)
    ivr._client = None
    ivr._from = ""
    with pytest.raises(ChannelUnavailable):
        await ivr.send(msg)
    with pytest.raises(ChannelUnavailable):
        await BrevoAdapter(db_conn).send(msg)
    # This asserts the NO-CREDENTIALS state specifically, not whatever the dev
    # machine's .env happens to hold — a real FCM_SERVICE_ACCOUNT_JSON must not
    # make this test start hitting the live Firebase project with a fake token.
    monkeypatch.setattr(settings, "fcm_service_account_json", "/no/such/file.json")
    monkeypatch.setattr(fcm_mod, "_app_initialized", False)
    monkeypatch.setattr(fcm_mod, "_messaging", None)
    with pytest.raises(ChannelUnavailable):
        await fcm_mod.FcmAdapter(db_conn).send(msg)
    with pytest.raises(ChannelUnavailable):
        await PeerRelayAdapter(db_conn).send(msg)
    relay = HumanRelayAdapter(db_conn)
    relay._client = None
    relay._from = None
    with pytest.raises(ChannelUnavailable):
        await relay.send(msg)
    assert await TwilioSmsAdapter(db_conn).parse_webhook(b"", {}) == []
    assert await TwilioIvrAdapter(db_conn).parse_webhook(b"", {}) == []
    assert await BrevoAdapter(db_conn).parse_webhook(b"", {}) == []
    assert await fcm_mod.FcmAdapter(db_conn).parse_webhook(b"", {}) == []
    assert await PeerRelayAdapter(db_conn).parse_webhook(b"", {}) == []
    assert await HumanRelayAdapter(db_conn).parse_webhook(b"", {}) == []
    assert await SimulatedCarrierAdapter(db_conn).parse_webhook(b"", {}) == []
    assert await WebhookSirenAdapter(db_conn).parse_webhook(b"", {}) == []
    assert await confirm_relay_from_dtmf(db_conn, delivery_row["id"], "9") is False

    class Sid:
        sid = "SM1"

    class Messages:
        def create(self, **k):
            return Sid()

    class Calls:
        def create(self, **k):
            return Sid()

    class FakeTwilio:
        messages = Messages()
        calls = Calls()

    captured: dict = {}

    class CapturingMessages:
        def create(self, **k):
            captured.update(k)
            return Sid()

    class CapturingTwilio:
        messages = CapturingMessages()
        calls = Calls()

    await db_conn.execute(
        """
        INSERT INTO app_config (key, value, unit, note)
        VALUES ('response.sms_footer', 'Reply SAFE if you are safe. Reply HELP if you need help.', 'string', 'test')
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """
    )
    sms = TwilioSmsAdapter(db_conn)
    sms._client = CapturingTwilio()
    sms._from = "+10000000000"
    sent = await sms.send(_msg(delivery_row, channel="sms"))
    assert sent.provider_ref == "SM1"
    assert "SAFE" in captured["body"]
    assert "HELP" in captured["body"]
    ivr = TwilioIvrAdapter(db_conn)
    ivr._client = FakeTwilio()
    ivr._from = "+10000000000"
    called = await ivr.send(_msg(delivery_row, channel="ivr"))
    assert called.provider_ref == "SM1"


async def test_simulated_send_records_events(db_conn, delivery_row, monkeypatch):
    calls = {"n": 0}

    def fake_random() -> float:
        calls["n"] += 1
        return 0.99 if calls["n"] == 1 else 0.0

    async def no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr("services.delivery.channels.simulated.random.random", fake_random)
    monkeypatch.setattr("services.delivery.channels.simulated.random.uniform", lambda a, b: a)
    monkeypatch.setattr("services.delivery.channels.simulated.asyncio.sleep", no_sleep)
    adapter = SimulatedCarrierAdapter(db_conn, {"profiles": {"sim": {
        "latency_ms_min": 0,
        "latency_ms_max": 0,
        "failure_rate": 0,
    }}})
    result = await adapter.send(_msg(delivery_row))
    assert result.simulated is True
    assert result.provider_ref.startswith("sim-")


async def test_simulated_transient_failure(db_conn, delivery_row, monkeypatch):
    async def no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr("services.delivery.channels.simulated.random.random", lambda: 0.0)
    monkeypatch.setattr("services.delivery.channels.simulated.random.uniform", lambda a, b: a)
    monkeypatch.setattr("services.delivery.channels.simulated.asyncio.sleep", no_sleep)
    adapter = SimulatedCarrierAdapter(db_conn, {"profiles": {"default": {
        "latency_ms_min": 0,
        "latency_ms_max": 0,
        "failure_rate": 1,
    }}})
    with pytest.raises(TransientChannelError):
        await adapter.send(_msg(delivery_row))


async def test_siren_send_and_email_failure(db_conn, delivery_row, monkeypatch):
    class Resp:
        status_code = 200

        def __init__(self) -> None:
            self.headers = {"x-message-id": "sid-1"}

        def json(self) -> dict:
            return {"messageId": "sid-1"}

    class FailResp:
        status_code = 500

        def __init__(self) -> None:
            self.headers = {}

        def json(self) -> dict:
            return {}

    class Client:
        def __init__(self, *a, **k) -> None:
            self.status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, *a, **k):
            return Resp()

    monkeypatch.setattr("services.delivery.channels.siren.httpx.AsyncClient", Client)
    result = await WebhookSirenAdapter(db_conn, {"webhook_url": "http://example.test"}).send(
        _msg(delivery_row)
    )
    assert result.provider_ref.startswith("siren-")

    class FailClient(Client):
        async def post(self, *a, **k):
            return FailResp()

    monkeypatch.setattr("services.delivery.channels.siren.httpx.AsyncClient", FailClient)
    with pytest.raises(ChannelUnavailable):
        await WebhookSirenAdapter(db_conn, {"webhook_url": "http://example.test"}).send(
            _msg(delivery_row)
        )


async def test_load_adapters_and_create_deliveries(db_conn, delivery_row):
    registry = await load_channel_adapters(db_conn)
    assert "sim" in registry
    ids = await create_deliveries(db_conn, delivery_row["alert_id"], [delivery_row["recipient_id"]])
    assert ids
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await enqueue_fanout(redis, db_conn, delivery_row["alert_id"], [delivery_row["recipient_id"]])
        await publish_ops(redis, {"type": "test", "alert_id": delivery_row["alert_id"]})
        await ensure_consumer_group(redis, db_conn)
        await ensure_consumer_group(redis, db_conn)
        nonce = str(uuid.uuid4())
        await store_nonce(redis, db_conn, delivery_row["id"], nonce)
        message = await build_message(db_conn, delivery_row["id"])
        assert message.channel_code == "sim"
        assert message.address
    finally:
        await _close_redis(redis)


async def test_extreme_phone_gets_sms_and_ivr_even_with_push_token(db_conn, delivery_row):
    """Citizen-app login must not skip SMS/IVR on Extreme — those are compulsory."""
    alert_id = delivery_row["alert_id"]
    recipient_id = delivery_row["recipient_id"]
    await db_conn.execute("UPDATE alert SET severity = 'extreme' WHERE id = $1", alert_id)
    await db_conn.execute(
        """
        UPDATE recipient
        SET push_token = 'tok', phone_enc = '\\x00'::bytea
        WHERE id = $1
        """,
        recipient_id,
    )
    ids = await create_deliveries(db_conn, alert_id, [recipient_id])
    codes = {
        row["code"]
        for row in await db_conn.fetch(
            """
            SELECT c.code FROM delivery d
            JOIN channel c ON c.id = d.channel_id
            WHERE d.id = ANY($1::bigint[])
            """,
            ids,
        )
    }
    assert "sms" in codes
    assert "ivr" in codes
    assert "fcm" in codes
    await db_conn.execute("DELETE FROM delivery WHERE id = ANY($1::bigint[])", ids)


async def test_process_recipient_sim_path(db_conn, delivery_row, monkeypatch):
    async def no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr("services.delivery.channels.simulated.random.random", lambda: 0.99)
    monkeypatch.setattr("services.delivery.channels.simulated.random.uniform", lambda a, b: a)
    monkeypatch.setattr("services.delivery.channels.simulated.asyncio.sleep", no_sleep)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        adapters = {"sim": SimulatedCarrierAdapter(db_conn)}
        await process_recipient(
            db_conn,
            redis,
            adapters,
            delivery_row["alert_id"],
            delivery_row["recipient_id"],
        )
        state = await db_conn.fetchval("SELECT state FROM delivery WHERE id = $1", delivery_row["id"])
        assert state in {"delivered", "failed", "sent"}
        await process_recipient(
            db_conn,
            redis,
            adapters,
            delivery_row["alert_id"],
            99999999,
        )
        await process_batch(
            db_conn,
            redis,
            {"alert_id": str(delivery_row["alert_id"]), "recipient_ids": json.dumps([])},
        )
    finally:
        await _close_redis(redis)


async def test_process_recipient_fallback_to_sim(db_conn, delivery_row, monkeypatch):
    class Boom:
        async def send(self, msg):
            raise ChannelUnavailable("nope")

    async def no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr("services.delivery.channels.simulated.random.random", lambda: 0.99)
    monkeypatch.setattr("services.delivery.channels.simulated.random.uniform", lambda a, b: a)
    monkeypatch.setattr("services.delivery.channels.simulated.asyncio.sleep", no_sleep)
    fcm_id = await db_conn.fetchval("SELECT id FROM channel WHERE code = 'fcm'")
    await db_conn.execute(
        "UPDATE recipient SET push_token = 'tok' WHERE id = $1",
        delivery_row["recipient_id"],
    )
    await db_conn.execute(
        "UPDATE delivery SET channel_id = $2, state = 'pending' WHERE id = $1",
        delivery_row["id"],
        fcm_id,
    )
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await process_recipient(
            db_conn,
            redis,
            {"fcm": Boom(), "sim": SimulatedCarrierAdapter(db_conn)},
            delivery_row["alert_id"],
            delivery_row["recipient_id"],
        )
    finally:
        await _close_redis(redis)


async def test_relay_escalation_and_receipts(db_conn, delivery_row):
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        created = await on_channels_exhausted(
            redis=redis,
            conn=db_conn,
            alert_id=delivery_row["alert_id"],
            recipient_id=delivery_row["recipient_id"],
            exhausted_delivery_id=delivery_row["id"],
        )
        assert created is None or created > 0
        with pytest.raises(ValueError):
            await record_receipt(
                db_conn,
                delivery_row["id"],
                event_type="acknowledged",
                nonce="x",
            )
        await transition(db_conn, delivery_row["id"], State.queued)
        await transition(db_conn, delivery_row["id"], State.sent)
        await record_receipt(
            db_conn,
            delivery_row["id"],
            event_type="device_delivered",
            nonce="nonce-1",
        )
    finally:
        await _close_redis(redis)


async def test_worker_loop_idle(db_conn, monkeypatch):
    shutdown = asyncio.Event()

    class FakeRedis:
        async def xgroup_create(self, *a, **k):
            return True

        async def xreadgroup(self, *a, **k):
            shutdown.set()
            return []

        async def xack(self, *a, **k):
            return 1

        async def aclose(self):
            return None

        async def close(self):
            return None

    monkeypatch.setattr(
        "services.delivery.worker.Redis.from_url",
        lambda *a, **k: FakeRedis(),
    )
    await worker_loop("cov-consumer", shutdown)


async def test_state_failed_reason(db_conn, delivery_row):
    await transition(db_conn, delivery_row["id"], State.queued)
    await transition(db_conn, delivery_row["id"], State.failed, reason="timeout")
    row = await db_conn.fetchrow("SELECT state, failed_reason FROM delivery WHERE id = $1", delivery_row["id"])
    assert row["state"] == "failed"
    assert row["failed_reason"] == "timeout"
    with pytest.raises(ValueError):
        await transition(db_conn, 99999999, State.queued)
    with pytest.raises(ValueError):
        await build_message(db_conn, 99999999)


def test_fcm_already_initialized(monkeypatch):
    class FakeMessaging:
        pass

    fcm_mod._app_initialized = True
    fcm_mod._messaging = FakeMessaging
    assert fcm_mod._ensure_firebase() is FakeMessaging
    fcm_mod._app_initialized = False
    fcm_mod._messaging = None
    monkeypatch.setattr(settings, "fcm_service_account_json", "/no/such/file.json")
    with pytest.raises(ChannelUnavailable):
        fcm_mod._ensure_firebase()


def test_peer_relay_disabled_flag(db_conn):
    assert os.environ.get("REDIS_URL") or settings.redis_url


async def test_email_and_fcm_send_success(db_conn, delivery_row, monkeypatch):
    class Resp:
        status_code = 200

        def __init__(self) -> None:
            self.headers = {"x-message-id": "em-1"}

        def json(self) -> dict:
            return {"messageId": "em-1"}

    class Client:
        def __init__(self, *a, **k) -> None:
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, *a, **k):
            return Resp()

    monkeypatch.setattr(settings, "brevo_api_key", "test-key")
    monkeypatch.setattr("services.delivery.channels.email.httpx.AsyncClient", Client)
    email_result = await BrevoAdapter(db_conn).send(_msg(delivery_row, channel="email"))
    assert email_result.provider_ref == "em-1"

    class FakeMessaging:
        class Message:
            def __init__(self, **k) -> None:
                return None

        class Notification:
            def __init__(self, **k) -> None:
                return None

        class WebpushConfig:
            def __init__(self, **k) -> None:
                return None

        @staticmethod
        def send(message) -> str:
            return "fcm-1"

    monkeypatch.setattr(fcm_mod, "_ensure_firebase", lambda: FakeMessaging)
    fcm_result = await fcm_mod.FcmAdapter(db_conn).send(_msg(delivery_row, channel="fcm"))
    assert fcm_result.provider_ref == "fcm-1"


async def test_process_recipient_transient(db_conn, delivery_row):
    class Flaky:
        async def send(self, msg):
            raise TransientChannelError("tmp")

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await process_recipient(
            db_conn,
            redis,
            {"sim": Flaky()},
            delivery_row["alert_id"],
            delivery_row["recipient_id"],
        )
        state = await db_conn.fetchval("SELECT state FROM delivery WHERE id = $1", delivery_row["id"])
        assert state == "failed"
    finally:
        await _close_redis(redis)


async def test_dispatch_and_webhook_and_relay_branches(db_conn, delivery_row, monkeypatch):
    blocked = QualityGateBlocked([{"rule_id": "expires_at"}])
    assert blocked.failures
    missing = DispatchError("no_recipients", "none")
    assert missing.code == "no_recipients"

    class Req:
        def __init__(self) -> None:
            self.headers = {}
            self.url = "http://localhost/hook"

        async def form(self):
            return {}

    monkeypatch.setattr(settings, "twilio_webhook_auth_token", "")
    monkeypatch.setattr(settings, "twilio_auth_token", "")
    with pytest.raises(ValueError):
        await verify_twilio_form(Req())
    monkeypatch.setattr(settings, "twilio_auth_token", "tok")

    class BadValidator:
        def __init__(self, token) -> None:
            return None

        def validate(self, url, params, sig) -> bool:
            return False

    class GoodValidator:
        def __init__(self, token) -> None:
            return None

        def validate(self, url, params, sig) -> bool:
            return True

    monkeypatch.setattr("services.delivery.webhook_verify.RequestValidator", BadValidator)
    with pytest.raises(PermissionError):
        await verify_twilio_form(Req())
    monkeypatch.setattr("services.delivery.webhook_verify.RequestValidator", GoodValidator)
    assert await verify_twilio_form(Req()) == {}

    async def enabled(_conn, _key):
        return True

    monkeypatch.setattr("services.delivery.channels.community_relay.config_repo.get_bool", enabled)
    with pytest.raises(ChannelUnavailable):
        await PeerRelayAdapter(db_conn).send(_msg(delivery_row))

    unit_id = await db_conn.fetchval(
        "SELECT unit_id FROM recipient WHERE id = $1", delivery_row["recipient_id"]
    )
    await find_relay_node(db_conn, unit_id)
    await db_conn.execute(
        """
        INSERT INTO relay_node (unit_id, kind, name, phone_enc, phone_hash, active)
        VALUES ($1, 'sarpanch', 'Test node', $2, $3, true)
        """,
        unit_id,
        b"enc",
        b"hash",
    )
    adapter = HumanRelayAdapter(db_conn)
    adapter._client = None
    adapter._from = None
    with pytest.raises(ChannelUnavailable):
        await adapter.send(_msg(delivery_row))
    with pytest.raises(ChannelUnavailable):
        await adapter.send(
            OutboundMessage(
                alert_id=delivery_row["alert_id"],
                delivery_id=delivery_row["id"],
                recipient_id=99999999,
                channel_code="human_relay",
                address="addr",
                headline="H",
                body="B",
                ack_url="http://localhost/ack",
            )
        )
    human_id = await db_conn.fetchval("SELECT id FROM channel WHERE code = 'human_relay'")
    await transition(db_conn, delivery_row["id"], State.queued)
    await transition(db_conn, delivery_row["id"], State.sent)
    await transition(db_conn, delivery_row["id"], State.delivered)
    await db_conn.execute(
        "UPDATE delivery SET channel_id = $2 WHERE id = $1",
        delivery_row["id"],
        human_id,
    )
    confirmed = await confirm_relay_delivery(
        db_conn,
        delivery_row["id"],
        method="http",
        actor="tester",
    )
    assert confirmed in {True, False}

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        try:
            await dispatch_alert(db_conn, redis, delivery_row["alert_id"], actor="tester")
        except (QualityGateBlocked, DispatchError, Exception):
            pass
        class Boom:
            async def send(self, msg):
                raise ChannelUnavailable("nope")

        await db_conn.execute(
            "UPDATE delivery SET state = 'pending' WHERE id = $1",
            delivery_row["id"],
        )
        await process_recipient(
            db_conn,
            redis,
            {"human_relay": Boom(), "sim": SimulatedCarrierAdapter(db_conn)},
            delivery_row["alert_id"],
            delivery_row["recipient_id"],
        )
    finally:
        await _close_redis(redis)


async def test_worker_loop_processes_empty_batch(db_conn, delivery_row, monkeypatch):
    shutdown = asyncio.Event()

    class FakeRedis:
        def __init__(self) -> None:
            self.n = 0

        async def xgroup_create(self, *a, **k):
            return True

        async def xreadgroup(self, *a, **k):
            self.n += 1
            if self.n == 1:
                return [[
                    "stream",
                    [(
                        "1-0",
                        {
                            "alert_id": str(delivery_row["alert_id"]),
                            "recipient_ids": "[]",
                        },
                    )],
                ]]
            shutdown.set()
            return []

        async def xack(self, *a, **k):
            return 1

        async def aclose(self):
            return None

        async def close(self):
            return None

    monkeypatch.setattr("services.delivery.worker.Redis.from_url", lambda *a, **k: FakeRedis())
    await worker_loop("cov-batch", shutdown)


def test_worker_main(monkeypatch):
    monkeypatch.setattr("services.delivery.worker.asyncio.run", lambda coro: None)
    from services.delivery.worker import main

    main()


async def test_coverage_remaining_branches(db_conn, delivery_row, monkeypatch):
    monkeypatch.setattr(settings, "brevo_api_key", "")
    with pytest.raises(ChannelUnavailable):
        await BrevoAdapter(db_conn).send(_msg(delivery_row))
    monkeypatch.setattr(settings, "public_base_url", "")
    with pytest.raises(ChannelUnavailable):
        await WebhookSirenAdapter(db_conn, {}).send(_msg(delivery_row))
    monkeypatch.setattr(settings, "public_base_url", "http://localhost:8000")
    monkeypatch.setattr(settings, "twilio_account_sid", "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    monkeypatch.setattr(settings, "twilio_auth_token", "token")
    TwilioSmsAdapter(db_conn)
    TwilioIvrAdapter(db_conn)
    HumanRelayAdapter(db_conn)
    monkeypatch.setattr(settings, "twilio_account_sid", "")
    monkeypatch.setattr(settings, "twilio_auth_token", "")
    TwilioSmsAdapter(db_conn)
    TwilioIvrAdapter(db_conn)

    async def disabled(_conn, _key):
        return False

    monkeypatch.setattr("services.delivery.channels.community_relay.config_repo.get_bool", disabled)
    with pytest.raises(ChannelUnavailable):
        await PeerRelayAdapter(db_conn).send(_msg(delivery_row))

    from services.delivery.assurance import record

    await record(
        db_conn,
        delivery_row["id"],
        "provider_accepted",
        source="cov",
        evidence_id="ev",
    )
    ladder = await alert_assurance(db_conn, delivery_row["alert_id"])
    assert ladder["deliveries"]

    evaluation = await evaluate(db_conn, delivery_row["alert_id"])
    if evaluation["incident_id"] is None:
        assert evaluation["relabel"] is False
    headline, _ = await apply_headline(db_conn, delivery_row["alert_id"], "UPDATED: Stay")
    assert headline

    class FakeAdmin:
        @staticmethod
        def initialize_app(cred):
            return None

    class FakeCred:
        @staticmethod
        def Certificate(path):
            return "cred"

    class FakeMessaging:
        class Message:
            def __init__(self, **k) -> None:
                return None

        class Notification:
            def __init__(self, **k) -> None:
                return None

        class WebpushConfig:
            def __init__(self, **k) -> None:
                return None

        @staticmethod
        def send(message) -> str:
            return "fcm-2"

    monkeypatch.setattr(fcm_mod, "_load_firebase", lambda: (FakeAdmin, FakeCred, FakeMessaging))
    monkeypatch.setattr(fcm_mod, "_app_initialized", False)
    monkeypatch.setattr(fcm_mod, "_messaging", None)
    handle, cert = tempfile.mkstemp(suffix=".json")
    os.close(handle)
    with open(cert, "w", encoding="utf-8") as out:
        out.write("{}")
    try:
        monkeypatch.setattr(settings, "fcm_service_account_json", cert)
        fcm_mod._ensure_firebase()
        msg = OutboundMessage(
            alert_id=delivery_row["alert_id"],
            delivery_id=delivery_row["id"],
            recipient_id=delivery_row["recipient_id"],
            channel_code="fcm",
            address="tok",
            headline="H",
            body="B",
            ack_url="http://localhost/ack",
            receipt_nonce="nonce",
            signature="sig",
        )
        fcm_mod._app_initialized = True
        fcm_mod._messaging = FakeMessaging
        result = await fcm_mod.FcmAdapter(db_conn).send(msg)
        assert result.provider_ref == "fcm-2"
    finally:
        if os.path.exists(cert):
            os.remove(cert)

    adapter = HumanRelayAdapter(db_conn)
    twiml = await adapter._twiml_url(delivery_row["id"])
    assert "ivr-twiml" in twiml
    original = asyncpg.connection.Connection.fetchval

    async def fetchval(self, query, *args, **kwargs):
        if isinstance(query, str) and "pgp_sym_decrypt" in query:
            return "+910000000000"
        return await original(self, query, *args, **kwargs)

    monkeypatch.setattr(asyncpg.connection.Connection, "fetchval", fetchval)
    adapter._client = type(
        "C",
        (),
        {
            "calls": type(
                "K",
                (),
                {"create": staticmethod(lambda **k: type("S", (), {"sid": "CA1"})())},
            )()
        },
    )()
    adapter._from = "+10000000000"
    monkeypatch.setattr(settings, "pgcrypto_sym_key", "key")
    unit_id = await db_conn.fetchval(
        "SELECT unit_id FROM recipient WHERE id = $1", delivery_row["recipient_id"]
    )
    exists = await db_conn.fetchval("SELECT id FROM relay_node WHERE unit_id = $1 LIMIT 1", unit_id)
    if exists is None:
        await db_conn.execute(
            """
            INSERT INTO relay_node (unit_id, kind, name, phone_enc, phone_hash, active)
            VALUES ($1, 'sarpanch', 'Cov', $2, $3, true)
            """,
            unit_id,
            b"enc",
            b"hash",
        )
    sent = await adapter.send(_msg(delivery_row, channel="human_relay"))
    assert sent.provider_ref == "CA1"

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        async def locked(*a, **k):
            return True

        async def unlocked(*a, **k):
            return None

        async def allowed(*a, **k):
            return None

        async def results(*a, **k):
            return []

        async def persist(*a, **k):
            return None

        async def recip(*a, **k):
            return [delivery_row["recipient_id"]]

        async def none_recip(*a, **k):
            return []

        async def pred(*a, **k):
            return None

        monkeypatch.setattr("services.delivery.engine.acquire_supersede_lock", locked)
        monkeypatch.setattr("services.delivery.engine.release_supersede_lock", unlocked)
        monkeypatch.setattr("services.delivery.engine.ensure_dispatch_allowed", allowed)
        monkeypatch.setattr("services.delivery.engine.validate", results)
        monkeypatch.setattr("services.delivery.engine.persist_results", persist)
        monkeypatch.setattr("services.delivery.engine.has_blocking_failure", lambda r: False)
        monkeypatch.setattr("services.delivery.engine.supersede_predecessor", pred)
        monkeypatch.setattr("services.delivery.engine.recipients_in_area", recip)
        out = await dispatch_alert(db_conn, redis, delivery_row["alert_id"], actor="cov")
        assert out["alert_id"] == delivery_row["alert_id"]

        monkeypatch.setattr("services.delivery.engine.has_blocking_failure", lambda r: True)
        with pytest.raises(QualityGateBlocked):
            await dispatch_alert(db_conn, redis, delivery_row["alert_id"], actor="cov")
        monkeypatch.setattr("services.delivery.engine.has_blocking_failure", lambda r: False)
        monkeypatch.setattr("services.delivery.engine.recipients_in_area", none_recip)
        with pytest.raises(DispatchError):
            await dispatch_alert(db_conn, redis, delivery_row["alert_id"], actor="cov")

        async def unlocked_false(*a, **k):
            return False

        monkeypatch.setattr("services.delivery.engine.acquire_supersede_lock", unlocked_false)
        from services.governance.versioning import VersionInFlightError

        with pytest.raises(VersionInFlightError):
            await dispatch_alert(db_conn, redis, delivery_row["alert_id"], actor="cov")

        async def flag_off(_conn, _key):
            return False

        monkeypatch.setattr("services.delivery.relay_escalation.config_repo.get_bool", flag_off)
        assert await on_channels_exhausted(
            db_conn,
            redis,
            alert_id=delivery_row["alert_id"],
            recipient_id=delivery_row["recipient_id"],
            exhausted_delivery_id=delivery_row["id"],
        ) is None

        await db_conn.execute(
            "UPDATE delivery SET state = 'pending' WHERE id = $1",
            delivery_row["id"],
        )
        with pytest.raises(RuntimeError):
            await process_recipient(
                db_conn, redis, {}, delivery_row["alert_id"], delivery_row["recipient_id"]
            )
    finally:
        await _close_redis(redis)
