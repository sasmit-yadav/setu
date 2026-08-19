-- data/seeds/06_app_users.sql — §5.5, Part 26 (RBAC matrix), Rule 12.
--
-- WHY THIS FILE EXISTS: F3 dual authorization is only real if TWO DISTINCT
-- officers can approve. UNIQUE (alert_id, approver_id) makes "the second
-- approval cannot be the same person" a database guarantee — but that
-- guarantee is untestable and the demo beat is unrunnable if only one officer
-- account exists. Before this file, the database had exactly one ad-hoc user
-- (a@test.local), so `ensure_dispatch_allowed` could be shown BLOCKING at
-- 0-of-2 but never shown UNBLOCKING, which is half the story.
--
-- These are LOCAL/DEMO accounts. They carry no password and no credential of
-- any kind — authentication (E1) is not built yet, and when it is, these rows
-- get real hashed credentials injected from the environment, never from this
-- committed file (see CLAUDE.md's secrets rule).
--
-- unit_scope_id is left NULL deliberately: Part 26 scopes officers to their
-- own district, but scoping is enforced in the API layer, and hardcoding a
-- specific admin_unit id here would break the moment geometry is reloaded
-- (ids are BIGSERIAL, not stable across a reload). Scope is assigned by
-- lookup at the point RBAC lands, not baked into a seed.

INSERT INTO app_user (email, role, unit_scope_id, active) VALUES
  -- Two DISTINCT officers: the entire point of the Four-Eyes beat. Officer A
  -- composes and approves; Officer B provides the independent second approval
  -- from a different login. One officer clicking twice yields ONE row
  -- (UNIQUE (alert_id, approver_id)) and never satisfies a quorum of 2.
  ('officer.a@setu.local',     'officer',     NULL, true),
  ('officer.b@setu.local',     'officer',     NULL, true),

  -- State admin: the only role permitted to close an incident (Part 26).
  ('state.admin@setu.local',   'state_admin', NULL, true),

  -- Auditor: sees proof the system behaved correctly, never the PII it
  -- protects. Aggregate-only on /assistance, no contact reveal (§12.2).
  ('auditor@setu.local',       'auditor',     NULL, true),

  -- Relay node operator: gets a COUNT AND AN AREA, never a household list.
  -- The row Part 26 says most implementations get wrong (§12.2).
  ('relay.node@setu.local',    'relay_node',  NULL, true),

  -- Citizen: the PWA's own role, lowest privilege.
  ('citizen@setu.local',       'citizen',     NULL, true)

-- Idempotent, for the same reason 03_alert_sources.sql is: a seed file is the
-- source of truth (Rule 3) and re-running it must CORRECT a drifted row
-- rather than silently skip it.
ON CONFLICT (email) DO UPDATE SET
  role   = EXCLUDED.role,
  active = EXCLUDED.active;
