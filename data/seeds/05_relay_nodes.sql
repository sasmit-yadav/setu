-- data/seeds/05_relay_nodes.sql — §4.7. Six demo relay nodes across the two
-- case-study districts, team members' OWN verified phones behind them
-- (Twilio trial reaches verified numbers only — Trap 5).
--
-- ⚠ PLACEHOLDER — phone_enc/phone_hash below are dummy values encrypted with
-- the word 'PLACEHOLDER'. This file MUST be re-run with real verified team
-- phone numbers before Day 5 (B9 human relay needs it) and Day 7 (D8f's
-- no_relay_coverage check needs at least one active node per case-study unit).
--
-- Real run looks like:
--   psql ... -v phone1='+91XXXXXXXXXX' -c "..."
-- or a small Python loader that calls phone_hash() with PHONE_HASH_PEPPER and
-- pgp_sym_encrypt() with PGCRYPTO_SYM_KEY. Do not hand-type ciphertext.
--
-- Wayanad and Palghar admin_unit rows do not exist until the ADM3/ADM5
-- geometry load (§1.6.2) runs, so this seed is a no-op (0 rows) until then —
-- that is correct, not a bug: relay_node.unit_id is NOT NULL and cannot
-- reference a unit that isn't loaded yet.
--
-- SPEC CORRECTION: "Wayanad" is a DISTRICT name, and geoBoundaries has no
-- admin_unit row literally named that at ADM3/ADM5 (sub-district/village)
-- resolution — confirmed by loading the real data. "Meppadi" (the specific
-- town the design doc's demo narrative names) also isn't a distinct
-- geoBoundaries shape at this resolution; its real coordinates
-- (~11.65N, 76.13E) fall inside the ADM5 village polygon actually named
-- "Muttil North" (confirmed via ST_Intersects against a point at those
-- coordinates). Palghar's demo town, "Talasari", DOES exist under that
-- exact name at both ADM3 and ADM5 — no substitution needed there.
--
-- Using the real containing units below. The pitch language ("Meppadi
-- Panchayat Office") stays as the human-readable NAME on each relay_node
-- row; unit_id points at the real polygon that geographically contains it.

DO $$
DECLARE
  wayanad_unit BIGINT;
  palghar_unit BIGINT;
BEGIN
  SELECT id INTO wayanad_unit FROM admin_unit WHERE name = 'Muttil North' AND level = 5 LIMIT 1;
  SELECT id INTO palghar_unit FROM admin_unit WHERE name = 'Talasari' AND level = 5 LIMIT 1;

  IF wayanad_unit IS NULL OR palghar_unit IS NULL THEN
    RAISE NOTICE 'relay_nodes.sql: Wayanad/Palghar admin_unit rows not loaded yet '
                  '(run scripts/fetch_data.sh + load_admin_units.py first). Skipping seed.';
    RETURN;
  END IF;

  INSERT INTO relay_node (unit_id, kind, name, phone_enc, phone_hash, active) VALUES
    (wayanad_unit, 'panchayat',     'Meppadi Panchayat Office (demo contact)',
       pgp_sym_encrypt('+91PLACEHOLDER1', 'CHANGE-ME'), decode('00', 'hex'), true),
    (wayanad_unit, 'police',        'Meppadi Police Station (demo contact)',
       pgp_sym_encrypt('+91PLACEHOLDER2', 'CHANGE-ME'), decode('01', 'hex'), true),
    (wayanad_unit, 'health_worker', 'ASHA -- Meppadi Ward 4 (demo contact)',
       pgp_sym_encrypt('+91PLACEHOLDER3', 'CHANGE-ME'), decode('02', 'hex'), true),
    (palghar_unit, 'panchayat',     'Talasari Panchayat Office (demo contact)',
       pgp_sym_encrypt('+91PLACEHOLDER4', 'CHANGE-ME'), decode('03', 'hex'), true),
    (palghar_unit, 'school',        'ZP School Talasari (demo contact)',
       pgp_sym_encrypt('+91PLACEHOLDER5', 'CHANGE-ME'), decode('04', 'hex'), true),
    (palghar_unit, 'volunteer',     'Registered volunteer -- Talasari (demo)',
       pgp_sym_encrypt('+91PLACEHOLDER6', 'CHANGE-ME'), decode('05', 'hex'), true);
END $$;
