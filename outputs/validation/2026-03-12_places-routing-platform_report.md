# Evidence Report — Google Places Routing to platform_v1

**Date:** 2026-03-12
**Branch:** feature/20260312-places-routing-platform
**Task:** Resolve Google Places routing — establish platform_v1.places as canonical schema

---

## Decision

`platform_v1.places` is the canonical Google Places schema for all platform services
and projects. Shogun reads place data via the Google Places REST gateway, not direct
database writes. `shogun_v1.places` has been dropped.

---

## Schema Comparison (pre-task)

Both `google_places` and `google_place_snapshots` were field-for-field identical across
both databases, with two minor differences:

- `shogun_v1.places.google_places.source_country` had a hardcoded default `'JP'::text`
  — Shogun-specific, not appropriate for a platform table. `platform_v1` had no default (correct).
- `platform_v1.places.google_places` had one additional index (`idx_google_places_country`)
  — platform_v1 was slightly more complete.

`neighborhood_anchors` existed only in `shogun_v1.places` — needed to be added to platform_v1.

---

## Actions Taken

### 1. Added `neighborhood_anchors` to `platform_v1.places` (dba-agent)

```sql
CREATE TABLE places.neighborhood_anchors (
    provider, neighborhood_id (PK), city, country, input_address,
    resolved_place_id, resolved_formatted_addr, resolved_country,
    lat, lng, resolution_method, raw_geocode_json,
    created_utc, updated_utc
);
CREATE INDEX idx_neighborhood_anchors_country ON places.neighborhood_anchors (country);
GRANT SELECT, INSERT, UPDATE ON places.neighborhood_anchors TO places_app;
GRANT SELECT ON places.neighborhood_anchors TO mcp_laptop_ro;
```

### 2. Google Places gateway config — already correct

`PGDATABASE=platform_v1` was already set in the gateway `.env` on svcnode-01.
The gateway was always targeting `platform_v1`. No config change required.
The 20 places / 60 snapshots in `shogun_v1.places` were written via direct testing,
not from the gateway.

### 3. Dropped `shogun_v1.places` schema (dba-agent)

```sql
DROP SCHEMA places CASCADE;
-- cascades to: google_places, google_place_snapshots, neighborhood_anchors
```

Confirmed: no Shogun containers were running. Test data only — no production loss.

### 4. Documentation updated

- `05-database.md`: routing table simplified, KNOWN ISSUE replaced with RESOLVED notice
- `platform_v1.md`: places schema updated with all 3 tables, "empty" note removed
- `shogun_v1.md`: places schema section removed, primary user updated, anti-pattern updated
- `planning-state.md`: Google Places routing open decision marked RESOLVED

---

## Verification

```sql
-- shogun_v1.places gone:
SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'places';
-- (0 rows) ✓

-- platform_v1.places has all 3 tables:
SELECT tablename FROM pg_tables WHERE schemaname = 'places' ORDER BY tablename;
-- google_place_snapshots
-- google_places
-- neighborhood_anchors ✓
```

---

## Green Gate Checklist

| # | Item | Status |
|:--|:-----|:-------|
| 1 | Validate PASS | SKIP — schema/routing change, no service code changed |
| 2 | Loki Level 1 | SKIP |
| 3 | OpenAPI spec | SKIP — no API changes |
| 4 | Capability registry | SKIP — no capability changes |
| 5 | _index.md | SKIP — no new service |
| 6 | Evidence report | PASS — this file |
| 7 | .env.example | SKIP — no new env vars |

---

## Outcome

**COMPLETE.** Architecture is clean. Platform owns place data. Shogun uses the REST
gateway. The Google Places routing open decision is closed. Shogun reboot can proceed.
