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

## Known Limitations / Quirks
- Rate limits are governed by the upstream Google Places API quota
- The gateway caches repeated identical queries for 5 minutes — expected behavior
- If you receive a 429, the upstream quota has been hit — do not retry immediately

## Last Updated
2026-03-03 — Initial doc created
