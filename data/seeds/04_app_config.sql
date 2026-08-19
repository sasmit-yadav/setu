-- data/seeds/04_app_config.sql — Part 21 + §21.4. Every threshold a row, with
-- a non-empty `note` a teammate could read aloud in Q&A (Rule 1).
--
-- Count note: §21.4's own heading claims "36 rows"; the actual v3.0 block
-- below contains more once counted honestly. scripts/verify_seeds.py checks
-- the REAL count emitted by this file, not the number the spec's prose used —
-- fixing that mismatch here rather than asserting a stale figure blindly.

-- ═══ Thunderstorm classifier + dedup (§21.2) ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('thunderstorm.cape_floor',    '1000', 'J/kg',  'Standard moderate-instability threshold'),
  ('thunderstorm.cape_scale',    '500',  'J/kg',  'Sigmoid steepness — tune only after real labels'),
  ('thunderstorm.li_ceiling',    '-2',   'K',     'Standard "thunderstorms likely" Lifted Index'),
  ('thunderstorm.li_scale',      '2',    'K',     'Sigmoid steepness'),
  ('thunderstorm.alert_floor',   '0.55', 'score', 'Risk above which a synthetic CAP alert is emitted — start conservative'),
  ('dedup.similarity_threshold', '0.72', 'cosine','Agglomerative cut — re-tune after the 200-pair label pass'),
  ('dedup.window_hours',         '6',    'hours', 'Bounds the O(n^2) pairwise comparison in cluster()');

-- ═══ Ingestion + delivery worker tuning ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('ingest.poll_lookback_hours', '24', 'hours', 'Default discover() window for ingestion pollers'),
  ('ingest.alert_default_ttl_hours', '24', 'hours', 'Default expires_at offset from effective_at'),
  ('ingest.http_timeout_s', '30', 'seconds', 'Default outbound HTTP timeout for ingestion adapters'),
  ('ingest.http_not_modified_status', '304', 'http', 'Treat as NotModified for conditional GET adapters'),
  ('ingest.usgs.time_ms_divisor', '1000', 'factor', 'USGS properties.time epoch milliseconds to seconds'),
  ('ingest.usgs.alert_radius_km', '50', 'km', 'Buffer around USGS epicenter for alert polygon'),
  ('ingest.usgs.mag_extreme', '7.0', 'mag', 'USGS magnitude floor for extreme severity'),
  ('ingest.usgs.mag_severe', '6.0', 'mag', 'USGS magnitude floor for severe severity'),
  ('ingest.usgs.mag_moderate', '5.0', 'mag', 'USGS magnitude floor for moderate severity'),
  ('ingest.gdacs.alert_radius_km', '75', 'km', 'Fallback buffer when GDACS returns a point geometry'),
  ('geo.km_to_meters', '1000', 'meters', 'Kilometres to metres conversion for ST_Buffer'),
  ('time.seconds_per_minute', '60', 'seconds', 'Minutes to seconds conversion'),
  ('http.status_client_error_min', '400', 'http', 'Outbound HTTP responses at or above this are failures'),
  ('delivery.xread_count', '10', 'messages', 'Redis XREADGROUP batch count'),
  ('delivery.xread_block_ms', '5000', 'ms', 'Redis XREADGROUP block timeout');

-- ═══ Simulated carrier profile (§8.5 — values in config, not code) ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('simulated.latency_ms_min', '10',  'ms',    'Simulated carrier minimum latency'),
  ('simulated.latency_ms_max', '200', 'ms',    'Simulated carrier maximum latency'),
  ('simulated.failure_rate',   '0.05','ratio', 'Simulated transient failure probability'),
  ('simulated.ms_to_seconds',  '0.001','factor','Milliseconds to seconds conversion for simulated latency');

-- ═══ System-wide (§21.3) ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('delivery.batch_size',             '100',   'recipients', '§6.2 — one XADD per this many'),
  ('delivery.stream_maxlen',          '10000', 'entries',    'Redis Streams cap, approximate trim'),
  ('redis.daily_command_budget',      '16600', 'commands',   'Alert at 80% = 13280, Part 28'),
  ('pwa.network_timeout_seconds',     '4',     'seconds',    'NetworkFirst cutover to cache'),
  ('pwa.alert_cache_max_age_seconds', '86400', 'seconds',    '24h — older than this is stale even offline'),
  ('pwa.ack_retention_minutes',       '1440',  'minutes',    'BackgroundSync gives up after this'),
  ('api.rate_limit_per_ip',           '60',    'req/min',    'slowapi default'),
  ('api.rate_limit_dispatch',         '5',     'req/min',    'Tighter on /dispatch'),
  ('jwt.access_ttl_minutes',          '15',    'minutes',    ''),
  ('jwt.refresh_ttl_days',            '7',     'days',       '');

-- ═══ F3 Dual Authorization (Rule 12) ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('approval.required.minor',    '1', 'approvals', 'One authorized officer is sufficient for an advisory'),
  ('approval.required.moderate', '1', 'approvals', 'One authorized officer is sufficient'),
  ('approval.required.severe',   '2', 'approvals', 'Independent second officer. UNIQUE(alert_id,approver_id) makes it structural'),
  ('approval.required.extreme',  '2', 'approvals', 'Independent second officer'),
  ('approval.authoritative_sources_auto_approve', 'true', 'bool',
     'A source flagged is_authoritative dispatches with provenance=authoritative_source, no human wait'),
  ('approval.wait_alert_seconds', '300', 'seconds', 'If unapproved this long, page the ops channel (Part 28)');

-- ═══ F1 Quality Gate ═══
-- NOTE ON required_lang: the spec's original single global 'ml' floor would
-- block or misvalidate Palghar (Maharashtra, Marathi) alerts. Keyed per unit's
-- state instead, via two rows rather than one — decided now, not discovered
-- when a real Palghar alert gets blocked in rehearsal.
INSERT INTO app_config (key, value, unit, note) VALUES
  ('quality_gate.min_target_count',    '1',     'recipients', 'An alert targeting zero recipients is always blocked'),
  ('quality_gate.max_target_area_km2', '50000', 'km2',        'Above this, WARN not BLOCK — larger than Kerala'),
  ('quality_gate.require_expiry',      'true',  'bool',       'An alert with no expiry poisons dedup and fatigue calculations'),
  ('quality_gate.required_lang_for_severe.KL',  'ml', 'lang', 'Kerala case-study state: Malayalam required for severe'),
  ('quality_gate.required_lang_for_severe.MH',  'mr', 'lang', 'Maharashtra case-study state (Palghar): Marathi, NOT Malayalam'),
  ('quality_gate.required_lang_for_extreme.KL', 'ml', 'lang', 'Same, for extreme'),
  ('quality_gate.required_lang_for_extreme.MH', 'mr', 'lang', 'Same, for extreme'),
  ('case_study.bbox.KL', '10.8,74.5,12.2,77.0', 'bbox', 'Kerala case-study region (Wayanad) — south,west,north,east'),
  ('case_study.bbox.MH', '19.3,72.6,20.2,73.4', 'bbox', 'Maharashtra case-study region (Palghar) — south,west,north,east');

-- ═══ F2 Versioning ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('versioning.cancel_inflight_on_supersede', 'true', 'bool',
     'A citizen reconnecting after v3 (evacuate) must not receive v1 from a retry queue'),
  ('versioning.supersede_lock_ms', '3000', 'ms', 'Redis SET NX PX window serialising two officers escalating the same incident');

-- ═══ F4 Alert Fatigue ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('fatigue.window_minutes',    '30', 'minutes', 'Lookback for related alerts on the same incident'),
  ('fatigue.alert_count_floor', '3',  'alerts',  'Third alert in the window triggers relabeling'),
  ('fatigue.relabel_prefix',    'URGENT UPDATE - ', 'string', 'Prepended at message-build time'),
  ('fatigue.never_suppress',    'true', 'bool',  'Hard invariant, asserted by a test — fatigue changes wording, never prevents delivery');

-- ═══ D8f Communication Vulnerability ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('vuln.tower_count_floor',          '2',   'towers',     'Fewer than 2 towers within 5km = single point of failure'),
  ('vuln.terrain_ruggedness_ceiling', '0.6', 'normalized', 'Above this, terrain itself obstructs signal — the Wayanad geometry'),
  ('vuln.historical_reach_floor_pct', '50',  'percent',    'A unit whose historical reach is below this is structurally vulnerable');

-- ═══ D11f Assistance Priority (Rule 10 — every weight explainable aloud) ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('assistance.weight_version', 'v1-2026-08-16', 'string', 'Stamped into every case so a score is reproducible'),
  ('assistance.weight.response_severity', '0.35', 'ratio', 'Largest single weight: trapped outranks everything'),
  ('assistance.weight.hazard_severity',   '0.25', 'ratio', 'The same request during extreme outranks moderate'),
  ('assistance.weight.vulnerability',     '0.15', 'ratio', 'Reuses the EXISTING reach-risk score — no new model'),
  ('assistance.weight.proximity',         '0.15', 'ratio', 'Distance to the hazard polygon, normalised'),
  ('assistance.weight.time_waiting',      '0.10', 'ratio', 'Smallest weight deliberately — waiting must never outrank newly trapped'),
  ('assistance.max_wait_minutes', '120', 'minutes', 'Normalisation ceiling for time_waiting'),
  ('assistance.wait_norm_max', '1', 'ratio', 'Maximum normalised wait factor'),
  ('assistance.response_severity.trapped',            '1.0', 'score', 'Immediate threat to life'),
  ('assistance.response_severity.medical',            '0.9', 'score', 'Immediate threat to life, may be stationary'),
  ('assistance.response_severity.unable_to_evacuate',  '0.7', 'score', 'Threatened but not yet in immediate danger'),
  ('assistance.response_severity.other',              '0.4', 'score', 'Unknown need — triaged by a human'),
  ('assistance.proximity_max_m', '50000', 'meters', 'Normalisation ceiling for proximity factor in D11f priority'),
  ('response.free_text_max_chars', '280', 'chars', 'Pydantic cap for C6 other free-text'),
  ('assistance.default_vulnerability', '0.5', 'normalized', 'Fallback when unit_features.terrain_ruggedness is NULL'),
  ('risk.top_factors_limit', '5', 'factors', 'Max factor rows returned by GET /units/{id}/risk'),
  ('alert.manual.default_radius_km', '25', 'km', 'Officer-composed point alert buffer when no polygon supplied'),
  ('api.idempotency_ttl_seconds', '86400', 'seconds', 'Redis TTL for dispatch idempotency replay cache'),
  ('api.version_conflict_retry_after_ms', '500', 'ms', 'Retry-After hint when supersede lock is held'),
  ('api.list_default_limit', '50', 'rows', 'Default LIMIT for list endpoints when caller omits ?limit='),
  ('geometry.admin_unit_batch_size', '500', 'rows', 'INSERT batch size for load_admin_units.py'),
  ('enrollment.sms_rate_limit_per_minute', '5', 'messages', 'Inbound SMS keyword rate limit per sender'),
  ('enrollment.sms_rate_window_seconds', '60', 'seconds', 'Rate limit window for inbound SMS keywords'),
  ('enrollment.sms_auto_reply_registered', 'SETU: You are registered for disaster alerts. Reply STOP to opt out.', 'string', 'Auto-reply after REGISTER'),
  ('enrollment.sms_auto_reply_stopped', 'SETU: You have been opted out. Reply REGISTER to re-enroll.', 'string', 'Auto-reply after STOP'),
  ('ivr.dtmf.safe', '1', 'digit', 'DTMF digit for I am safe'),
  ('ivr.dtmf.need_help', '2', 'digit', 'DTMF digit opening assistance submenu'),
  ('ivr.dtmf.trapped', '1', 'digit', 'Assistance submenu: trapped'),
  ('ivr.dtmf.medical', '2', 'digit', 'Assistance submenu: medical'),
  ('ivr.dtmf.unable_to_evacuate', '3', 'digit', 'Assistance submenu: unable to evacuate'),
  ('ivr.prompt.main', 'Press {safe} if you are safe. Press {need_help} if you need help.', 'string', 'IVR Gather prompt'),
  ('severity.rank.extreme',  '1.0',  'score', 'Shared severity ranking, used by priority and elsewhere'),
  ('severity.rank.severe',   '0.75', 'score', ''),
  ('severity.rank.moderate', '0.5',  'score', ''),
  ('severity.rank.minor',    '0.2',  'score', '');

-- ═══ B9 Human Relay ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('relay.escalate_on_channels_exhausted', 'true', 'bool', '§7.4 — the branch that makes channels_exhausted not the end of the line'),
  ('relay.node_kind_priority', 'panchayat,police,health_worker,school,volunteer,shelter', 'csv',
     'Order relay nodes are tried. Institutional before individual'),
  ('relay.confirm_timeout_minutes', '20', 'minutes', 'No DTMF confirmation in this window -> re-call once, then relay.unconfirmed');

-- ═══ B8 Assurance + B10 Peer Relay ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('assurance.receipt_nonce_ttl_minutes', '240', 'minutes', 'A SW receipt nonce is valid this long'),
  ('pwa.receipt_retention_minutes', '1440', 'minutes', 'BackgroundSync retention for receipts'),
  ('relay.peer_enabled', 'true', 'bool', 'Kill switch — one UPDATE hides B10 entirely with no redeploy'),
  ('relay.peer_max_hops', '1', 'hops', 'ONE. Peer relay, not mesh. NOTE (Day-4 spike): browsers expose no GATT peripheral/server role, so device-to-device relay may not be implementable as specced — see docs/day4-bluetooth-spike.md');

-- ═══ Assurance tier floors (a POLICY decision, Part 38 violation B) ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('reachability.reached_tier_floor',      '2', 'tier', 'Tier 2 = device_delivered. Provider-acceptance is explicitly NOT "reached"'),
  ('reachability.acknowledged_tier_floor', '4', 'tier', 'Tier 4 = acknowledged. A human acted');

-- ═══ IVR Gather (Part 38 violation E) ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('ivr.gather_digits',   '1',  'digits',  'Single keypress — works for a stressed, low-literacy user'),
  ('ivr.gather_timeout_s','10', 'seconds', 'Ten seconds is generous on purpose — tune on real demo calls');

-- ═══ B10 chunking (Part 38 violation D) ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('relay.peer_chunk_bytes', '480', 'bytes', 'Below the common BLE default MTU payload after ATT overhead');

-- ═══ Basemap (§1.6.5) ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('map.tile_source', 'pmtiles_local', 'enum',
     'pmtiles_local | openfreemap. MUST be pmtiles_local for the demo — a hosted basemap goes BLANK offline');

-- ═══ E4 Enrollment ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('enrollment.sms_keyword_register', 'REGISTER', 'string', 'Inbound keyword; case-insensitive'),
  ('enrollment.sms_keyword_stop',     'STOP',     'string', 'Opt-out. Honoured immediately and permanently, TRAI-aligned'),
  ('enrollment.csv_max_rows',         '5000',     'rows',   'Per-import cap'),
  ('enrollment.csv_require_dry_run',  'true',     'bool',   'A destructive bulk write must be previewed first'),
  ('enrollment.phone_local_digits',   '10',       'digits', 'National significant number length without country code'),
  ('enrollment.phone_country_digits', '12',       'digits', 'E.164 length including India country code 91');
