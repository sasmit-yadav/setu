-- data/seeds/03_alert_sources.sql — §4.2, §4.5. Adding a source is one INSERT.
-- is_authoritative drives Rule 12: USGS/GDACS are external authorities and
-- auto-approve; our OWN thunderstorm nowcast is is_authoritative=false and
-- does NOT get to authorize its own extreme alerts (§9.5).

INSERT INTO alert_source (source_id, class_path, config, poll_interval_s, is_authoritative, enabled) VALUES
  ('usgs', 'services.ingestion.adapters.usgs.UsgsAdapter',
   '{"feed_url": "https://earthquake.usgs.gov/fdsnws/event/1/query",
     "bbox": {"minlatitude": 6, "maxlatitude": 38, "minlongitude": 68, "maxlongitude": 98},
     "timeout_s": 30, "not_modified_status": 304}'::jsonb,
   300, true, true),

  ('gdacs', 'services.ingestion.adapters.gdacs.GdacsAdapter',
   '{"list_url": "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH",
     "india_bbox": {"minlatitude": 6, "maxlatitude": 38, "minlongitude": 68, "maxlongitude": 98},
     "timeout_s": 30, "not_modified_status": 304}'::jsonb,
   300, true, true),

  -- enabled=false until services/ingestion/adapters/thunderstorm.py exists.
  -- The row is seeded now so the source_id, its Rule 12 is_authoritative=false
  -- stance, and its poll interval are all reviewable in git before the code
  -- lands — but a source cannot be "enabled" when its adapter is unwritten.
  ('thunderstorm_nowcast', 'services.ingestion.adapters.thunderstorm.ThunderstormNowcastAdapter',
   '{"base_url": "https://api.open-meteo.com/v1/forecast"}'::jsonb,
   900, false, false),  -- [v3.0] our own model — NOT authoritative (Rule 12)

  -- 'manual' is a PROVENANCE, not a feed. Officer-composed alerts arrive via
  -- POST /api/v1/alerts (the composer), never by polling — so there is no
  -- ManualAdapter class and enabled=false is correct, not a gap. The row must
  -- still exist because alert.source_id references it and Rule 12 reads
  -- is_authoritative=false from it to require two human approvals.
  ('manual', 'services.ingestion.adapters.manual.ManualAdapter',
   '{}'::jsonb, 0, false, false),

  ('sachet', 'services.ingestion.adapters.sachet.SachetAdapter',
   '{"base_url": "https://sachet.ndma.gov.in/cap_public_website",
     "discovery_url": "UNVERIFIED-set-before-enabling"}'::jsonb,
   300, true, false),   -- [S] stretch — enabled:false until discovery endpoint confirmed (Trap 3)

  ('imd', 'services.ingestion.adapters.imd.ImdAdapter',
   '{"base_url": "https://api.imd.gov.in/public"}'::jsonb,
   300, true, false)   -- Trap 2: all endpoints return 401 as of Aug 2026 — disabled

-- Upsert, not a bare INSERT: this file is the SOURCE OF TRUTH for adapter
-- wiring (Rule 3), so re-running it must CORRECT a drifted row, not silently
-- skip it. Found the hard way — the database held an older gdacs config
-- pointing at .../geteventlist/MAP (which returns 400 "Eventtype is required")
-- and missing timeout_s/not_modified_status, while this file already had the
-- correct /SEARCH URL. A plain INSERT ... nothing meant re-seeding could never
-- fix it.
ON CONFLICT (source_id) DO UPDATE SET
  class_path       = EXCLUDED.class_path,
  config           = EXCLUDED.config,
  poll_interval_s  = EXCLUDED.poll_interval_s,
  is_authoritative = EXCLUDED.is_authoritative,
  enabled          = EXCLUDED.enabled;
