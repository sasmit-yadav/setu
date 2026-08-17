-- data/seeds/03_alert_sources.sql — §4.2, §4.5. Adding a source is one INSERT.
-- is_authoritative drives Rule 12: USGS/GDACS are external authorities and
-- auto-approve; our OWN thunderstorm nowcast is is_authoritative=false and
-- does NOT get to authorize its own extreme alerts (§9.5).

INSERT INTO alert_source (source_id, class_path, config, poll_interval_s, is_authoritative, enabled) VALUES
  ('usgs', 'services.ingestion.adapters.usgs.UsgsAdapter',
   '{"feed_url": "https://earthquake.usgs.gov/fdsnws/event/1/query",
     "bbox": {"minlatitude": 6, "maxlatitude": 38, "minlongitude": 68, "maxlongitude": 98}}'::jsonb,
   300, true, true),

  ('gdacs', 'services.ingestion.adapters.gdacs.GdacsAdapter',
   '{"base_url": "https://www.gdacs.org/gdacsapi/api/events/geteventlist/MAP"}'::jsonb,
   300, true, true),

  ('thunderstorm_nowcast', 'services.ingestion.adapters.thunderstorm.ThunderstormNowcastAdapter',
   '{"base_url": "https://api.open-meteo.com/v1/forecast"}'::jsonb,
   900, false, true),   -- [v3.0] our own model — NOT authoritative (Rule 12)

  ('manual', 'services.ingestion.adapters.manual.ManualAdapter',
   '{}'::jsonb, 0, false, true),

  ('sachet', 'services.ingestion.adapters.sachet.SachetAdapter',
   '{"base_url": "https://sachet.ndma.gov.in/cap_public_website",
     "discovery_url": "UNVERIFIED-set-before-enabling"}'::jsonb,
   300, true, false),   -- [S] stretch — enabled:false until discovery endpoint confirmed (Trap 3)

  ('imd', 'services.ingestion.adapters.imd.ImdAdapter',
   '{"base_url": "https://api.imd.gov.in/public"}'::jsonb,
   300, true, false);   -- Trap 2: all endpoints return 401 as of Aug 2026 — disabled
