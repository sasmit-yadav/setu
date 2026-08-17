"""0001_extensions_and_geography

Base spec §5.1 (v2.1, unchanged). Extensions + admin_unit + unit_features +
safe_zone. Everything downstream is geometry against admin_unit, so this has
to be revision zero.

Revision ID: 0001
Revises:
Create Date: 2026-08-16
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS postgis')
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')

    op.execute("""
        CREATE TABLE admin_unit (
            id             BIGSERIAL PRIMARY KEY,
            lgd_code       BIGINT UNIQUE,
            level          SMALLINT NOT NULL,
            name           TEXT NOT NULL,
            parent_id      BIGINT REFERENCES admin_unit(id),
            geom           GEOMETRY(MultiPolygon, 4326) NOT NULL,
            centroid       GEOGRAPHY(Point, 4326) GENERATED ALWAYS AS
                             (ST_Centroid(geom)::geography) STORED,
            population     INTEGER,
            building_count INTEGER,
            source_id      TEXT NOT NULL,
            fetched_at     TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute('CREATE INDEX admin_unit_geom_gix ON admin_unit USING GIST (geom)')
    op.execute('CREATE INDEX admin_unit_level_ix ON admin_unit (level)')

    op.execute("""
        CREATE TABLE unit_features (
            unit_id            BIGINT PRIMARY KEY REFERENCES admin_unit(id),
            terrain_ruggedness NUMERIC,
            tower_count_5km    INTEGER,
            nearest_tower_km   NUMERIC,
            mean_elevation_m   NUMERIC,
            computed_at        TIMESTAMPTZ NOT NULL,
            feature_version    TEXT NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE safe_zone (
            id         BIGSERIAL PRIMARY KEY,
            name       TEXT,
            kind       TEXT NOT NULL,
            geom       GEOGRAPHY(Point, 4326) NOT NULL,
            unit_id    BIGINT REFERENCES admin_unit(id),
            source_id  TEXT NOT NULL DEFAULT 'osm_overpass',
            fetched_at TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute('CREATE INDEX safe_zone_geom_gix ON safe_zone USING GIST (geom)')


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS safe_zone')
    op.execute('DROP TABLE IF EXISTS unit_features')
    op.execute('DROP TABLE IF EXISTS admin_unit')
    # Extensions are left in place — dropping postgis/pgcrypto/pg_trgm on a
    # shared dev database is more likely to break a teammate's session than
    # to help anyone, and nothing downstream re-creates them.
