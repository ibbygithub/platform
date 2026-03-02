# Google Places Service

HTTP wrapper around the Google Places API (New). Provides text search and nearby search with environment-driven defaults for region, language, field masks, and radius.

## Endpoints

| FQDN | Purpose |
|------|---------|
| `places.platform.ibbytech.com` | Google Places API gateway |

## Quick Start

```bash
cp .env.example .env    # fill in GOOGLE_PLACES_API_KEY
docker compose up --build -d
curl https://places.platform.ibbytech.com/health
```

## API

### `GET /health`
```json
{ "status": "ok" }
```

### `POST /v1/places/search_text`
Keyword search with location bias. An anchor (`lat`/`lng`) is required.

```json
{
  "text_query": "ramen",
  "lat": 34.6937,
  "lng": 135.5023,
  "radius_m": 1000,
  "max_results": 10,
  "region_code": "JP",
  "language_code": "ja"
}
```

### `POST /v1/places/nearby`
Type-based search with strict location restriction.

```json
{
  "included_types": ["ramen_restaurant"],
  "lat": 34.6937,
  "lng": 135.5023,
  "radius_m": 500
}
```

## Database Setup

Run once on `dbnode-01`:
```bash
psql -U dba-agent -d platform_v1 -f sql/001_create_places_schema.sql
```

## Field Masks

Control which Google fields are returned (and billed). Set in `.env` — no spaces allowed.
- `GOOGLE_TEXTSEARCH_FIELDMASK` — used by `/v1/places/search_text`
- `GOOGLE_NEARBY_FIELDMASK` — used by `/v1/places/nearby`
- `GOOGLE_DETAILS_FIELDMASK` — reserved for future enrichment endpoints
