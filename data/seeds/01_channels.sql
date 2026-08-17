-- data/seeds/01_channels.sql — Rule 3: seeded data, never a Python/TS literal.
-- §21.1. channel_id mapping: 1=fcm 2=email 3=sms 4=ivr 5=siren 6=sim 7=human_relay 8=community_relay

INSERT INTO channel (code, class_path, config, cost_weight) VALUES
  ('fcm',   'services.delivery.channels.fcm.FcmAdapter',               '{}'::jsonb, 0),
  ('email', 'services.delivery.channels.email.BrevoAdapter',           '{}'::jsonb, 0),
  ('sms',   'services.delivery.channels.sms.TwilioSmsAdapter',         '{}'::jsonb, 5),
  ('ivr',   'services.delivery.channels.ivr.TwilioIvrAdapter',         '{}'::jsonb, 8),
  ('siren', 'services.delivery.channels.siren.WebhookSirenAdapter',    '{}'::jsonb, 1),
  ('sim',   'services.delivery.channels.simulated.SimulatedCarrierAdapter', '{}'::jsonb, 0),
  ('human_relay',     'services.delivery.channels.human_relay.HumanRelayAdapter',       '{}'::jsonb, 12),
  ('community_relay', 'services.delivery.channels.community_relay.PeerRelayAdapter',    '{}'::jsonb, 0);

-- EXTREME: skip straight to push, escalate fast, exhaust every channel — then a human (§7.4)
INSERT INTO escalation_policy
  (severity, step_order, channel_id, wait_before_next_s, backoff_multiplier, jitter_ms,
   max_attempts, applies_if_reach_risk_gte)
SELECT 'extreme', 1, id, 90,  1.5, 5000, 2, NULL::NUMERIC FROM channel WHERE code = 'fcm'
UNION ALL SELECT 'extreme', 2, id, 60,  1.5, 5000, 2, NULL::NUMERIC FROM channel WHERE code = 'sms'
UNION ALL SELECT 'extreme', 3, id, 45,  1.0, 2000, 1, NULL::NUMERIC FROM channel WHERE code = 'ivr'
UNION ALL SELECT 'extreme', 4, id, 0,   1.0, 0,    1, NULL::NUMERIC FROM channel WHERE code = 'siren'
UNION ALL SELECT 'extreme', 5, id, 120, 1.0, 0,    2, NULL::NUMERIC FROM channel WHERE code = 'human_relay';

-- EXTREME + high predicted reach-risk: skip fcm, go straight to sms (the Palghar fix, §7.3)
-- step_order=0 sorts first; fires at risk >= 0.65
INSERT INTO escalation_policy
  (severity, step_order, channel_id, wait_before_next_s, backoff_multiplier, jitter_ms,
   max_attempts, applies_if_reach_risk_gte)
SELECT 'extreme', 0, id, 60, 1.5, 5000, 2, 0.65 FROM channel WHERE code = 'sms';

-- SEVERE: same channels, longer waits, human relay still available
INSERT INTO escalation_policy
  (severity, step_order, channel_id, wait_before_next_s, backoff_multiplier, jitter_ms,
   max_attempts, applies_if_reach_risk_gte)
SELECT 'severe', 1, id, 180, 1.5, 8000, 2, NULL::NUMERIC FROM channel WHERE code = 'fcm'
UNION ALL SELECT 'severe', 2, id, 120, 1.5, 8000, 2, NULL::NUMERIC FROM channel WHERE code = 'sms'
UNION ALL SELECT 'severe', 3, id, 300, 1.0, 0,    1, NULL::NUMERIC FROM channel WHERE code = 'email'
UNION ALL SELECT 'severe', 4, id, 300, 1.0, 0,    1, NULL::NUMERIC FROM channel WHERE code = 'human_relay';

-- MODERATE: push + email only, no SMS spend, no relay (a human's time is the most expensive channel)
INSERT INTO escalation_policy
  (severity, step_order, channel_id, wait_before_next_s, backoff_multiplier, jitter_ms,
   max_attempts, applies_if_reach_risk_gte)
SELECT 'moderate', 1, id, 300, 1.5, 10000, 2, NULL::NUMERIC FROM channel WHERE code = 'fcm'
UNION ALL SELECT 'moderate', 2, id, 600, 1.0, 0,     1, NULL::NUMERIC FROM channel WHERE code = 'email';

-- MINOR: single push, no escalation
INSERT INTO escalation_policy
  (severity, step_order, channel_id, wait_before_next_s, backoff_multiplier, jitter_ms,
   max_attempts, applies_if_reach_risk_gte)
SELECT 'minor', 1, id, 0, 1.0, 0, 1, NULL::NUMERIC FROM channel WHERE code = 'fcm';
