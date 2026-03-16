# Service: Google Places Gateway

## Status
Active

## What This Service Does
Provides location search, place details, ratings, reviews, and geographic data
via the Google Places API. Use this for any task requiring place lookups,
business searches, or location-based queries.

## Endpoint
- **FQDN:** `https://places.platform.ibbytech.com`
- **Fallback IP:** `http://192.168.71.220` (use if DNS fails)
- **Target Node:** svcnode-01
- **Reverse Proxy:** Traefik

## Authentication
- **Method:** Bearer Token
- **Env Variable:** `PLACES_API_KEY`
- **Scope:** Google Places API — search, details, photos, geocoding

## Call Context

| Where You Are | URL to Use |
|:---|:---|
| Laptop (dev/test) | `https://places.platform.ibbytech.com` |
| brainnode-01 (production app) | `https://places.platform.ibbytech.com` or fallback IP |
| Inside svcnode-01 container | Internal Docker network name |

## Consumption (Python)

```python
import os
import requests

def search_places(query: str, location: str) -> dict:
    """Search for places using the IbbyTech Google Places gateway."""
    endpoint = os.getenv("PLACES_GATEWAY_URL", "https://places.platform.ibbytech.com")
    api_key = os.getenv("PLACES_API_KEY")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "query": query,
        "location": location
    }

    response = requests.post(f"{endpoint}/search", headers=headers, json=payload)
    response.raise_for_status()
    return response.json()

# Example: Find best rated ramen in Osaka
results = search_places("best rated ramen", "Osaka, Japan")
```

## Observability
- **Loki Label:** `{service="google-places-gateway"}`
- **Grafana Dashboard:** Not yet configured
- All API calls are logged — check Loki for request volume and error rates

## Capabilities

Capability registry for Stage 2 Part B (Capability Pre-check).

| Capability | Our Endpoint | Status | Last Verified |
|:-----------|:-------------|:-------|:--------------|
| Text search by keyword + location | `POST /v1/places/search_text` | `implemented` | 2026-03-11 |
| Nearby search by place type | `POST /v1/places/nearby` | `implemented` | 2026-03-11 |
| Photo proxy (key-safe image delivery) | `GET /v1/places/photo` | `implemented` | 2026-03-11 |
| Place details (hours, website, phone) | Not exposed | `available-upstream` | 2026-03-11 |
| Autocomplete (text suggestions as you type) | Not exposed | `available-upstream` | 2026-03-11 |
| Geocoding (address → lat/lng) | Not exposed | `available-upstream` | 2026-03-11 |
| Structured Loki logging | Not implemented | `not-available` | 2026-03-11 |

**Status definitions:**
- `implemented` — available and tested in the platform gateway
- `available-upstream` — supported by Google Places API but not yet exposed in app.py
- `not-available` — not implemented and no upstream path available

**Observability gap:** app.py (Flask) has no Loki push code. Container stdout is
the only log source. Fixing requires adding Loki push calls to each route handler
(separate task).

**Field mask note:** The gateway uses a fixed field mask (`GOOGLE_TEXTSEARCH_FIELDMASK`
/ `GOOGLE_NEARBY_FIELDMASK` env vars). To expose additional fields like `photos`,
`openingHours`, or `websiteUri`, update the field mask in `.env` on svcnode-01.

**Last Updated:** 2026-03-11 — Platform Test Standard Phase 3 applied. OpenAPI spec
added at `services/places-google/openapi.yaml`. Validate script added at
`services/places-google/validate_places.py`.

---

## Known Limitations / Quirks
- Rate limits are governed by the upstream Google Places API quota
- The gateway caches repeated identical queries for 5 minutes — expected behavior
- If you receive a 429, the upstream quota has been hit — do not retry immediately

## Last Updated
2026-03-03 — Initial doc created
