-- Platform Places schema
-- Run on dbnode-01 as dba-agent:
--   psql -U dba-agent -d platform_v1 -f 001_create_places_schema.sql

BEGIN;

CREATE SCHEMA IF NOT EXISTS places;

CREATE TABLE IF NOT EXISTS places.google_places (
  place_id                TEXT PRIMARY KEY,
  display_name            TEXT,
  primary_type            TEXT,
  types                   TEXT[],
  formatted_address       TEXT,
  lat                     DOUBLE PRECISION,
  lng                     DOUBLE PRECISION,

  google_maps_uri         TEXT,
  website_uri             TEXT,
  international_phone     TEXT,

  rating                  DOUBLE PRECISION,
  user_rating_count       INTEGER,
  price_level             TEXT,

  open_now                BOOLEAN,
  opening_hours_json      JSONB,
  payment_options_json    JSONB,

  source_neighborhood_id  TEXT,
  source_city             TEXT,
  source_country          TEXT,

  last_details_fetch_utc  TIMESTAMPTZ,
  last_nearby_fetch_utc   TIMESTAMPTZ,

  raw_details_json        JSONB,
  raw_nearby_json         JSONB,

  created_utc             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_utc             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_google_places_city    ON places.google_places(source_city);
CREATE INDEX IF NOT EXISTS idx_google_places_country ON places.google_places(source_country);
CREATE INDEX IF NOT EXISTS idx_google_places_geo     ON places.google_places(lat, lng);

CREATE TABLE IF NOT EXISTS places.google_place_snapshots (
  id               BIGSERIAL PRIMARY KEY,
  place_id         TEXT        NOT NULL,
  snapshot_type    TEXT        NOT NULL,   -- nearby | details | textsearch
  snapshot_utc     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  neighborhood_id  TEXT,
  raw_json         JSONB       NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_google_snapshots_place ON places.google_place_snapshots(place_id);
CREATE INDEX IF NOT EXISTS idx_google_snapshots_time  ON places.google_place_snapshots(snapshot_utc DESC);

COMMIT;
