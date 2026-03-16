# Service: Tavily Gateway

**Version:** 1.0.0
**Node:** svcnode-01
**FQDN:** `tavily.platform.ibbytech.com`
**Container:** `platform-tavily`
**Port:** 8084 (internal); routed via Traefik on 80/443
**Protocol:** HTTP / REST
**Deploy path:** `/opt/git/work/platform/services/tavily/`
**Persona:** devops-agent

---

## Purpose

AI-native web search via [Tavily](https://app.tavily.com). Supports kanji +
English queries and domain-restricted searches. Primary consumer is shogun-core
on brainnode-01.

**Key use cases:**
- General Japan travel search (restaurants, POIs, transit, local info)
- Kanji queries — Tavily handles Japanese natively, no transliteration needed
- Tabelog domain-restricted search — `include_domains: ["tabelog.com"]` for
  restaurant-specific results
- RAG pipeline: Tavily discovers URLs → Firecrawl (scraper service) extracts
  full content → pgvector embeds → LLM Gateway reasons

---

## Auth

No client auth on platform_net. TAVILY_API_KEY is held server-side in the
container's environment. Consumers do not need the key — they call the gateway.

---

## Endpoints

### GET /health

Returns gateway health and Tavily API reachability.

```json
{
  "ok": true,
  "time": 1741737600,
  "tavily_key_set": true,
  "tavily_status": 200
}
```

### POST /v1/search

Web search with optional domain restriction.

**Request:**
```json
{
  "query":           "東京 おすすめ ラーメン",
  "search_depth":    "basic",
  "max_results":     5,
  "include_domains": ["tabelog.com"],
  "include_answer":  false
}
```

| Field | Type | Default | Notes |
|:------|:-----|:--------|:------|
| `query` | string | required | Supports kanji + English |
| `search_depth` | `"basic"` \| `"advanced"` | `"basic"` | advanced = deeper, slower (~5-10s) |
| `max_results` | int 1–20 | 5 | |
| `include_domains` | list[str] | null | Restrict to these domains (e.g. `["tabelog.com"]`) |
| `exclude_domains` | list[str] | null | Exclude these domains |
| `include_answer` | bool | false | Tavily AI summary of results |
| `include_raw_content` | bool | false | Full page text in results |
| `include_images` | bool | false | Image URLs in results |

**Response:**
```json
{
  "ok": true,
  "query": "東京 おすすめ ラーメン",
  "results": [
    {
      "title": "...",
      "url": "https://tabelog.com/...",
      "content": "...",
      "score": 0.92
    }
  ],
  "answer": null,
  "response_time": 1.23
}
```

---

## Environment Variables

| Variable | Required | Description |
|:---------|:---------|:------------|
| `TAVILY_API_KEY` | Yes | Standard API key from app.tavily.com (NOT MCP key) |
| `LOKI_URL` | No | Defaults to `http://192.168.71.220:3100` |

The `.env` file lives at `/opt/git/work/platform/services/tavily/.env` on
svcnode-01. Created by the operator directly on the node — never committed.

---

## Consumption (Python — shogun-core)

```python
import os
import requests

TAVILY_URL = os.getenv("TAVILY_GATEWAY_URL", "http://tavily.platform.ibbytech.com")

def search(query: str, include_domains: list[str] | None = None,
           max_results: int = 5, search_depth: str = "basic") -> list[dict]:
    """Search via Tavily platform gateway."""
    payload = {
        "query":        query,
        "max_results":  max_results,
        "search_depth": search_depth,
    }
    if include_domains:
        payload["include_domains"] = include_domains

    r = requests.post(f"{TAVILY_URL}/v1/search", json=payload, timeout=30)
    r.raise_for_status()
    return r.json().get("results", [])


# Tabelog restaurant search
results = search("大阪 ラーメン おすすめ", include_domains=["tabelog.com"])

# General Japan travel search
results = search("Nakano Broadway opening hours vintage anime")
```

---

## Observability

- **Loki labels:** `service=tavily`, `level=info|error`, `node=svcnode-01`
- **View logs:** `docker logs --tail 50 platform-tavily`

---

## Rate Limits / Cost

Tavily charges per API call. Use `search_depth: "basic"` for most queries —
`"advanced"` costs more and is slower. The Shogun use case is low-volume
(triggered by user requests, not automated polling).

---

## Known Limitations / Quirks

- Domain restriction (`include_domains`) is best-effort — Tavily may still
  return results outside the domain if coverage is thin.
- Tavily may not index all Tabelog pages; supplement with Firecrawl for
  specific restaurant URLs when needed.
- No response caching at the gateway layer. If repeated identical queries
  are expected, add Valkey caching in the consumer (shogun-core).

---

## Last Updated

2026-03-12 — Initial service deployed
