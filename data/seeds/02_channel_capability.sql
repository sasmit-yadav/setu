-- data/seeds/02_channel_capability.sql — the Rule 8 honesty table, per-tier
-- (schema fix: migration 0009 uses channel_capability_tier, one row per
-- channel x tier, rather than the single not_applicable_reason column §8.2's
-- SQL used — that shape prints the WRONG reason against unsupported tiers
-- whenever a channel fails more than one, e.g. email's device_delivered vs
-- opened, or siren's three unsupported tiers sharing one sentence).

INSERT INTO channel_capability_tier (channel_id, tier, supported, device_delivered_source, not_applicable_reason)
SELECT id, 'provider_accept', true, NULL, NULL FROM channel WHERE code = 'fcm'
UNION ALL SELECT id, 'device_delivered', true, 'pwa_service_worker_callback', NULL FROM channel WHERE code = 'fcm'
UNION ALL SELECT id, 'opened', true, NULL, NULL FROM channel WHERE code = 'fcm'
UNION ALL SELECT id, 'acknowledgement', true, NULL, NULL FROM channel WHERE code = 'fcm';

INSERT INTO channel_capability_tier (channel_id, tier, supported, device_delivered_source, not_applicable_reason)
SELECT id, 'provider_accept', true, NULL, NULL FROM channel WHERE code = 'email'
UNION ALL SELECT id, 'device_delivered', false, NULL,
    'Email open tracking requires a tracking pixel. We do not use one: it is a privacy '
    'intrusion, it is blocked by most clients, and a blocked pixel is indistinguishable '
    'from an unopened email — so the signal would be unreliable as well as invasive.'
    FROM channel WHERE code = 'email'
UNION ALL SELECT id, 'opened', false, NULL,
    'Same reason as device_delivered: we declined to build open-pixel tracking (§8.2).'
    FROM channel WHERE code = 'email'
UNION ALL SELECT id, 'acknowledgement', true, NULL, NULL FROM channel WHERE code = 'email';

INSERT INTO channel_capability_tier (channel_id, tier, supported, device_delivered_source, not_applicable_reason)
SELECT id, 'provider_accept', true, NULL, NULL FROM channel WHERE code = 'sms'
UNION ALL SELECT id, 'device_delivered', true, 'twilio_carrier_status_callback', NULL FROM channel WHERE code = 'sms'
UNION ALL SELECT id, 'opened', false, NULL,
    'No mobile carrier exposes SMS read receipts to the sender. This tier cannot be '
    'measured for SMS by anyone, including us.'
    FROM channel WHERE code = 'sms'
UNION ALL SELECT id, 'acknowledgement', true, NULL, NULL FROM channel WHERE code = 'sms';

INSERT INTO channel_capability_tier (channel_id, tier, supported, device_delivered_source, not_applicable_reason)
SELECT id, 'provider_accept', true, NULL, NULL FROM channel WHERE code = 'ivr'
UNION ALL SELECT id, 'device_delivered', true, 'twilio_call_status_in_progress', NULL FROM channel WHERE code = 'ivr'
UNION ALL SELECT id, 'opened', false, NULL,
    'A voice call has no "opened" concept. Answering the call is the delivery, and the '
    'keypad press is the acknowledgement.'
    FROM channel WHERE code = 'ivr'
UNION ALL SELECT id, 'acknowledgement', true, NULL, NULL FROM channel WHERE code = 'ivr';

INSERT INTO channel_capability_tier (channel_id, tier, supported, device_delivered_source, not_applicable_reason)
SELECT id, 'provider_accept', true, NULL, NULL FROM channel WHERE code = 'siren'
UNION ALL SELECT id, 'device_delivered', false, NULL,
    'A siren or public-address broadcast produces no digital receipt of any kind. '
    'Confirmation requires a human — see the field relay channel.'
    FROM channel WHERE code = 'siren'
UNION ALL SELECT id, 'opened', false, NULL,
    'A physical broadcast has no "opened" concept at all.'
    FROM channel WHERE code = 'siren'
UNION ALL SELECT id, 'acknowledgement', false, NULL,
    'A siren cannot receive an acknowledgement; only a human relay or a citizen who '
    'later opens the PWA can confirm anything about a siren-only delivery.'
    FROM channel WHERE code = 'siren';

INSERT INTO channel_capability_tier (channel_id, tier, supported, device_delivered_source, not_applicable_reason)
SELECT id, 'provider_accept', true, NULL, NULL FROM channel WHERE code = 'sim'
UNION ALL SELECT id, 'device_delivered', true, 'simulated_carrier_profile', NULL FROM channel WHERE code = 'sim'
UNION ALL SELECT id, 'opened', true, NULL, NULL FROM channel WHERE code = 'sim'
UNION ALL SELECT id, 'acknowledgement', true, NULL, NULL FROM channel WHERE code = 'sim';

INSERT INTO channel_capability_tier (channel_id, tier, supported, device_delivered_source, not_applicable_reason)
SELECT id, 'provider_accept', true, NULL, NULL FROM channel WHERE code = 'human_relay'
UNION ALL SELECT id, 'device_delivered', true, 'relay_node_answered_call', NULL FROM channel WHERE code = 'human_relay'
UNION ALL SELECT id, 'opened', false, NULL,
    'A physical, door-to-door broadcast has no "opened" event.'
    FROM channel WHERE code = 'human_relay'
UNION ALL SELECT id, 'acknowledgement', true, 'relay_node_answered_call',
    'The relay operator''s keypad confirmation is a human attestation, recorded '
    'separately from digital delivery (Rule 9) — see relay_confirmation, not delivery_event.'
    FROM channel WHERE code = 'human_relay';
-- NOTE: acknowledgement above is `supported=true` with a reason attached — the reason
-- here documents WHERE the evidence lives (relay_confirmation), not that it's missing.
-- Rule 9's separation is enforced by the table split (§5.9), not by hiding the tier.

INSERT INTO channel_capability_tier (channel_id, tier, supported, device_delivered_source, not_applicable_reason)
SELECT id, 'provider_accept', false, NULL,
    'A peer-to-peer transfer never touches our server, so there is no provider to accept it.'
    FROM channel WHERE code = 'community_relay'
UNION ALL SELECT id, 'device_delivered', true, 'peer_gatt_write_signature_verified', NULL
    FROM channel WHERE code = 'community_relay'
UNION ALL SELECT id, 'opened', true, NULL, NULL FROM channel WHERE code = 'community_relay'
UNION ALL SELECT id, 'acknowledgement', true, NULL, NULL FROM channel WHERE code = 'community_relay';
