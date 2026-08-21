from __future__ import annotations

from services.crypto.alert_signing import sign_payload, verify_payload


def test_tampered_relay_payload_is_never_accepted():
    payload = {
        "alert_id": 1,
        "delivery_id": 2,
        "headline": "Evacuate",
        "severity": "extreme",
        "effective_at": "2026-08-19T12:00:00+00:00",
    }
    signature = sign_payload(payload)
    assert verify_payload(payload, signature) is True
    tampered = dict(payload)
    tampered["headline"] = "Stay home"
    assert verify_payload(tampered, signature) is False
