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
  ('thunderstorm.precip_probability_scale', '100', 'percent', 'Open-Meteo precipitation_probability is 0-100; divide to unit interval'),
  ('thunderstorm.geometry_level', '3', 'level', 'Poll ADM3 centroids, not every village'),
  ('thunderstorm.max_units_per_poll', '40', 'units', 'Open-Meteo courtesy budget per nowcast cycle'),
  ('thunderstorm.max_concurrent_fetches', '4', 'requests', 'In-flight Open-Meteo requests per poll'),
  ('thunderstorm.severity.extreme', '0.85', 'score', 'Nowcast risk floor for extreme'),
  ('thunderstorm.severity.severe', '0.70', 'score', 'Nowcast risk floor for severe'),
  ('thunderstorm.severity.moderate', '0.55', 'score', 'Nowcast risk floor for moderate'),
  ('ingest.thunderstorm_nowcast.alert_radius_km', '25', 'km', 'Buffer around the scored ADM3 centroid'),
  ('dedup.similarity_threshold', '0.72', 'cosine','Agglomerative cut — re-tune after the 200-pair label pass'),
  ('dedup.window_hours',         '6',    'hours', 'Bounds the O(n^2) pairwise comparison in cluster()'),
  ('dedup.spatial_radius_m',     '50000','meters', 'Spatial veto radius for ingest clustering'),
  ('dedup.eval_held_out_ratio',  '0.25', 'ratio', 'Held-out fraction for the labelled pair evaluation published on Methodology'),
  ('geo.earth_radius_m',         '6371000', 'meters', 'Mean Earth radius for haversine in the shipping spatial dedup eval'),
  ('time.seconds_per_hour',      '3600', 'seconds', 'Hours to seconds for the spatial/temporal window'),
  ('ml.http_timeout_s',          '8',    'seconds', 'API→HF Space /translate and /embed timeout. Dispatch never waits on this path for cached demo alerts'),
  ('ml.target_langs',            'ml,mr', 'csv', 'Languages pre-cached for case-study delivery surfaces when the ML service is reachable'),
  ('ml.translate.model_name',    'indictrans2_en_indic_dist_200m', 'id', 'model_registry name written only after a real /translate response is cached'),
  ('ml.translate.model_version', '0.1', 'version', 'Registry version for the isolated IndicTrans2 service'),
  ('ml.translate.hf_id',         'ai4bharat/indictrans2-en-indic-dist-200M', 'huggingface', 'Real IndicTrans2 card. The API never loads these weights; SETU_TRANSLATE_HF_ID on the ML process must match'),
  ('ml.embed.model_name',        'minilm_multilingual_l12_v2', 'id', 'model_registry name written only when /embed returns vectors'),
  ('ml.embed.model_version',     '0.1', 'version', 'Registry version for the isolated MiniLM service'),
  ('ml.embed.hf_id',             'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', 'huggingface', 'Real MiniLM card. SETU_EMBED_HF_ID on the ML process must match'),
  ('dedup.model_name',           'dedup_spatial_temporal', 'id', 'Shipping clusterer: PostGIS ST_DWithin + time window. MiniLM is a veto only when /embed is up'),
  ('dedup.model_version',        '0.1', 'version', 'Registry version for the spatial/temporal shipping model'),
  ('reach_risk.model_name',      'reach_risk_bootstrap', 'id', 'Weighted structural formula until labelled acknowledgements exist — always is_bootstrap'),
  ('reach_risk.model_version',   '0.1', 'version', 'Registry version for the bootstrap reach-risk formula'),
  ('reach_risk.case_study_name', 'reach_risk_case_study', 'id', 'Registry name for the n=2 named-unit case study'),
  ('reach_risk.case_study_version', '0.1', 'version', 'Registry version for the case-study disclosure row'),
  ('translation.fallback_notice', 'Shown in the original language. A translation was not in the cache.', 'string', 'Visible C3 fallback — never invents IndicTrans2 output'),
  ('reach_risk.case_study_unit_names', 'Wayanad,Palghar', 'csv', 'Named units for the n=2 case-study disclosure'),
  ('reach_risk.case_study_flag_floor', '0.5', 'score', 'Bootstrap score at or above this is reported as flagged for the case study'),
  ('reach_risk.disclosure.bootstrap', 'Bootstrap model pending real-world acknowledgement data.', 'string', 'Shown on unit risk when the prediction row is the bootstrap formula'),
  ('reach_risk.disclosure.missing', 'Bootstrap reach-risk model — no labelled acknowledgement outcomes exist yet. Structural vulnerability view shown where prediction is unavailable.', 'string', 'Shown when no reach_prediction row exists'),
  ('methodology.limitation.geometry', 'Nationwide village polygons do not fit the free database; targeting is ADM3 nationally and ADM5 in the case-study states.', 'string', 'Published on /methodology — not a code comment'),
  ('methodology.limitation.opencellid', 'OpenCelliD returned zero India rows; vulnerability tower features degrade honestly.', 'string', 'Published on /methodology'),
  ('methodology.limitation.reach_risk', 'Reach-risk is a bootstrap model until acknowledgement outcomes exist.', 'string', 'Published on /methodology'),
  ('methodology.limitation.dedup', 'Dedup that ships is PostGIS spatial/temporal clustering. MiniLM embeddings veto a cluster only when the isolated ML service /embed returns vectors.', 'string', 'Published on /methodology'),
  ('methodology.limitation.imd', 'IMD and SACHET remain stretch until credentials exist.', 'string', 'Published on /methodology'),
  ('thunderstorm.forecast_days', '1', 'days', 'Open-Meteo hourly window scored per nowcast poll');

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
  ('delivery.xread_block_ms', '15000', 'ms', 'Redis XREADGROUP block timeout. Raised from 5000: B3''s drain_due_retries() issues a ZPOPMIN on every idle tick, so at 5s this alone cost 17,280 commands/day before one alert dispatched -- more than Upstash''s whole daily budget. 15s cuts idle-tick cost 3x for 10s of added worst-case retry latency, which is immaterial against the policy''s own 45-120s wait_before_next_s values. See docs/IMPLEMENTATION.md §12.2.'),
  ('delivery.xread_socket_timeout_grace_s', '5', 'seconds', 'Added to xread_block_ms to derive the Redis client socket timeout. MUST be > 0: if the socket timeout is not longer than the blocking read, an IDLE worker times out and exits, and idle is a delivery worker''s normal state between alerts.');

-- ═══ Simulated carrier profile (§8.5 — values in config, not code) ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('simulated.latency_ms_min', '10',  'ms',    'Simulated carrier minimum latency'),
  ('simulated.latency_ms_max', '200', 'ms',    'Simulated carrier maximum latency'),
  ('simulated.failure_rate',   '0.05','ratio', 'Simulated transient failure probability'),
  ('simulated.ms_to_seconds',  '0.001','factor','Milliseconds to seconds conversion for simulated latency'),
  ('simulated.device_delivered_rate', '0.92', 'ratio', 'Of messages the simulated carrier ACCEPTS, the share it then confirms reached a device. Deliberately below 1.0: provider-accepted is not device-delivered, and a ladder where every accepted message always arrives would teach the officer the wrong thing. Every row it produces is simulated=true and SIM-badged.'),
  ('delivery.simulate_when_unaddressable', 'true', 'bool', 'When a recipient has no address for the policy channel (no push token, no phone), route them to the simulated carrier instead of failing the send. Trap 5 / §8.5: nationwide real SMS needs TRAI DLT registration, so most recipients run the identical engine against a simulated carrier, flagged simulated=true and badged SIM. Set false to make unaddressable recipients fail loudly instead — which is the honest choice once real addresses exist.');

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
  ('jwt.access_ttl_minutes',          '15',    'minutes',    'Access tokens are stateless and therefore CANNOT be revoked — this ttl is the revocation window. Kept short deliberately; the refresh flow makes it invisible to users.'),
  ('jwt.refresh_ttl_days',            '7',     'days',       'Refresh sessions are stored server-side and rotated on every use, so they CAN be revoked. Presenting an already-used token revokes the whole family (theft detection).'),
  ('auth.bcrypt_rounds',              '12',    'rounds',     'bcrypt work factor for NEW password hashes. 12 is the common present-day floor; raise it as hardware improves. Stored hashes carry their own cost, so raising this does not invalidate existing passwords.'),
  ('auth.citizen_otp_ttl_seconds',    '300',   'seconds',    'Citizen login OTP lifetime. Short because the code is a bearer credential.'),
  ('auth.citizen_otp_resend_seconds', '45',    'seconds',    'Minimum gap before a new OTP replaces the previous one for the same number.'),
  ('auth.citizen_otp_max_attempts',   '5',     'tries',      'Wrong codes after this many tries burn the challenge. Request a new one.');

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
  ('ivr.prompt.thanks', 'Thank you. SETU has recorded your response.', 'string', 'Spoken after a DTMF key so Twilio receives TwiML, not an empty 204'),
  ('severity.rank.extreme',  '1.0',  'score', 'Shared severity ranking, used by priority and elsewhere'),
  ('severity.rank.severe',   '0.75', 'score', 'Shared severity ranking, used by priority and elsewhere'),
  ('severity.rank.moderate', '0.5',  'score', 'Shared severity ranking, used by priority and elsewhere'),
  ('severity.rank.minor',    '0.2',  'score', 'Shared severity ranking, used by priority and elsewhere');

-- ═══ B9 Human Relay ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('recipient.device_kinds', 'village_siren', 'csv', 'Recipient kinds that are village hardware, not people — excluded from every count the desk labels "people", still targeted for delivery'),
  ('relay.escalate_on_channels_exhausted', 'true', 'bool', '§7.4 — the branch that makes channels_exhausted not the end of the line'),
  ('relay.node_kind_priority', 'panchayat,police,health_worker,school,volunteer,shelter', 'csv',
     'Order relay nodes are tried. Institutional before individual'),
  ('delivery.extreme_channel_delay_s', 'ivr:10', 'csv', 'Absolute delay per channel on an Extreme fan-out, seconds from dispatch. Push and SMS are unlisted so they go together; the voice call waits so the handset is not ringing while the message lands. Not an escalation — every channel still goes. Empty = all at once'),
  ('relay.silence_minutes', '15', 'minutes', 'A phone that was reached but has not replied for this long is a village that may not have heard — the desk suggests a runner, it does not send one'),
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
     'pmtiles_local | openfreemap. MUST be pmtiles_local for the demo — a hosted basemap goes BLANK offline'),
  ('map.openfreemap_style_url', 'https://tiles.openfreemap.org/styles/dark', 'url', 'Local-dev convenience tiles only — never the demo path'),
  ('map.geometry_level', '3', 'level', 'Choropleth uses ADM3 nationwide'),
  ('map.simplify_tolerance', '0.01', 'degrees', 'ST_Simplify before shipping GeoJSON to the console'),
  ('map.max_features', '800', 'features', 'Live map feature cap per bbox request'),
  ('map.india_min_lon', '68', 'degrees', 'South-Asia bbox matching ingest'),
  ('map.india_min_lat', '6', 'degrees', 'South-Asia bbox matching ingest'),
  ('map.india_max_lon', '98', 'degrees', 'South-Asia bbox matching ingest'),
  ('map.india_max_lat', '38', 'degrees', 'South-Asia bbox matching ingest'),
  ('map.default_zoom', '5', 'zoom', 'Initial live-map zoom for the India bbox'),
  ('map.pmtiles_min_bytes', '2048', 'bytes', 'HEAD Content-Length above this means a Protomaps extract, not the empty placeholder writer'),
  ('board.worst_units_limit', '3', 'units', 'D9f board lists this many worst D8f units'),
  ('relay.peer_service_uuid', '8e7f3c10-5a2b-4d91-9c4e-1f2a3b4c5d6e', 'uuid',
     'Web Bluetooth GATT service advertised for B10 one-tap peer relay'),
  ('relay.peer_char_uuid', '8e7f3c11-5a2b-4d91-9c4e-1f2a3b4c5d6e', 'uuid',
     'GATT characteristic that carries the chunked signed alert payload'),
  ('assistance.status_sequence', 'new,assigned,en_route,assisted,closed', 'csv', 'D11f assignment state machine'),
  ('relay.dtmf.confirm', '1', 'digit', 'DTMF that writes relay_confirmation.confirmed_by_human'),
  ('relay.prompt.confirm', 'This is SETU. Press 1 to confirm you will physically relay this alert in your unit.', 'string', 'B9 TwiML prompt'),
  ('reach_risk.weight.tower_gap', '0.45', 'ratio', 'Bootstrap reach-risk weight for missing towers'),
  ('reach_risk.weight.terrain', '0.35', 'ratio', 'Bootstrap reach-risk weight for ruggedness'),
  ('reach_risk.weight.elevation', '0.20', 'ratio', 'Bootstrap reach-risk weight for elevation'),
  ('reach_risk.elevation_scale_m', '1500', 'meters', 'Normalisation ceiling for elevation in bootstrap reach-risk'),
  ('safe_zone.candidate_limit', '8', 'rows', 'Nearest-shelter candidates considered for C4'),
  ('safe_zone.search_radius_m', '20000', 'meters', 'C4 search radius from the citizen or unit centroid');

-- ═══ E4 Enrollment ═══
INSERT INTO app_config (key, value, unit, note) VALUES
  ('enrollment.sms_keyword_register', 'REGISTER', 'string', 'Inbound keyword; case-insensitive'),
  ('enrollment.sms_keyword_stop',     'STOP',     'string', 'Opt-out. Honoured immediately and permanently, TRAI-aligned'),
  ('response.sms_keyword.safe', 'SAFE', 'string', 'Inbound SMS: same meaning as the PWA I am safe button'),
  ('response.sms_keyword.help', 'HELP', 'string', 'Inbound SMS: same meaning as I need help'),
  ('response.sms_reply.safe', 'SETU: Marked safe. Thank you.', 'string', 'Auto-reply after SAFE'),
  ('response.sms_reply.help', 'SETU: Help request received. Teams will be notified.', 'string', 'Auto-reply after HELP'),
  ('response.sms_reply.no_alert', 'SETU: No live warning for this number.', 'string', 'Auto-reply when SAFE/HELP has no active delivery'),
  ('response.sms_reply.hint', 'SETU: Reply SAFE if you are safe. Reply HELP if you need help.', 'string', 'Auto-reply for an unrecognised inbound word'),
  ('response.sms_footer', 'Reply SAFE if you are safe. Reply HELP if you need help.', 'string', 'Appended to every outbound warning SMS'),
  ('enrollment.csv_max_rows',         '5000',     'rows',   'Per-import cap'),
  ('enrollment.csv_require_dry_run',  'true',     'bool',   'A destructive bulk write must be previewed first'),
  ('enrollment.phone_local_digits',   '10',       'digits', 'National significant number length without country code'),
  ('enrollment.phone_country_digits', '12',       'digits', 'E.164 length including India country code 91');

INSERT INTO app_config (key, value, unit, note) VALUES
  ('api.deliveries_list_limit', '200', 'rows', 'Default LIMIT for GET /alerts/{id}/deliveries when caller omits ?limit='),
  ('ui.ladder_extra_sample', '8', 'ladders', 'After one ladder per channel, extra most-recent ladders on Alert Detail'),
  ('response.help_types', 'trapped,medical,unable_to_evacuate,other', 'csv', 'C6 help choices shown in the citizen PWA'),
  ('response.label.safe', 'I am safe', 'string', 'Citizen primary action'),
  ('response.label.help', 'I need help', 'string', 'Citizen secondary action'),
  ('response.label.trapped', 'I am trapped', 'string', 'C6 help type label'),
  ('response.label.medical', 'Medical help', 'string', 'C6 help type label'),
  ('response.label.unable_to_evacuate', 'Cannot evacuate', 'string', 'C6 help type label'),
  ('response.label.other', 'Something else', 'string', 'C6 help type label'),
  ('response.location_prompt_types', 'trapped', 'csv', 'C6 types that ask for GPS at the moment of tap'),
  ('response.free_text_types', 'other', 'csv', 'C6 types that open a free-text field'),
  ('response.geolocation_timeout_ms', '15000', 'ms', 'Browser geolocation timeout when C6 asks for a point'),
  ('response.safe_type', 'safe', 'string', 'C6 type that acknowledges without opening an assistance case');

INSERT INTO app_config (key, value, unit, note) VALUES
  ('demo.citizen_email', 'citizen@setu.example', 'email',
     'PWA email-fallback prefill only — never a password. Public config.'),
  ('demo.citizen_phone', '9000000000', 'phone',
     'PWA phone-login prefill. Public config. Maps to the Muttil North citizen account.'),
  ('demo.citizen_otp', '246810', 'otp',
     'Accepted only when Twilio is unset, and only for demo.citizen_phone. Not public config.'),
  ('demo.password_emails', 'officer.a@setu.example,officer.b@setu.example,state.admin@setu.example,auditor@setu.example,relay.node@setu.example,citizen@setu.example', 'csv',
     'Accounts that receive SETU_DEMO_PASSWORD at provision time. Hash only; password stays in .env.'),
  ('demo.unit_scope.officer.a@setu.example', 'Vythiri', 'name',
     'geoBoundaries ADM3 containing Muttil North / Meppadi. Wayanad is not an ADM3/ADM5 name.'),
  ('demo.unit_scope.officer.b@setu.example', 'Vythiri', 'name',
     'geoBoundaries name; provision prefers the lowest level (district over village).'),
  ('demo.unit_scope.citizen@setu.example', 'Muttil North', 'name',
     'ADM5 polygon that contains Meppadi (~11.65N, 76.13E). Same unit as 05_relay_nodes.sql.'),
  ('demo.unit_scope.relay.node@setu.example', 'Muttil North', 'name',
     'ADM5 polygon that contains Meppadi. Same unit as 05_relay_nodes.sql.');
