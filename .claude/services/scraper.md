# Service: Scraper

## Status
Active — All four endpoints (scrape, crawl, map, extract) fully operational.
Auto-persists results + OpenAI embeddings to Postgres (pgvector). Semantic similarity
search validated end-to-end. Only gap: Loki logging not yet implemented.

## What This Service Does
Scrapes and crawls web pages via a self-hosted Firecrawl instance; exposes single-page
scrape, multi-page crawl, URL-map discovery, and LLM-based structured extraction
through a platform-consistent FastAPI wrapper. Use this service whenever an agent needs
to retrieve web content or extract structured data from a URL.

## Endpoint
- **FQDN:** `https://scrape.platform.ibbytech.com`
- **Fallback IP:** `http://192.168.71.220:8083` (bypasses Traefik; use only if DNS is unavailable)
- **Target Node:** svcnode-01
- **Reverse Proxy:** Traefik (HTTPS termination on port 443 → container port 8083)
- **Firecrawl backend:** `http://192.168.71.220:3002` — self-hosted, LAN-only, not via Traefik

## Authentication
- **Method:** None — the scraper-api wrapper has no inbound auth enforcement
- **Env Variable:** `FIRECRAWL_API_KEY` (set to `local-no-auth` in `.env`; forwarded to
  Firecrawl which ignores it because `USE_DB_AUTHENTICATION=false`)
- **Scope:** Open on `platform_net` and via Traefik FQDN. Do not expose externally
  without adding auth middleware.

## Call Context

| Where You Are | URL to Use |
|:---|:---|
| Laptop (dev / test) | `https://scrape.platform.ibbytech.com` |
| brainnode-01 (production app) | `https://scrape.platform.ibbytech.com` |
| Inside svcnode-01 container (`platform_net`) | `http://platform-scraper-api:8083` |
| Direct to Firecrawl (skip wrapper) | `http://192.168.71.220:3002` — LAN only |

## API Reference

### `GET /health`
Reports whether the wrapper, Firecrawl backend, and database are up.
```json
{
  "ok": true,
  "time": 1709500000,
  "firecrawl_reachable": true,
  "db_connected": true,
  "persist_enabled": true,
  "embed_provider": "openai",
  "embed_model": "text-embedding-3-small"
}
```

### `POST /v1/scrape`
Scrape a single URL. Returns markdown, HTML, and metadata.
```json
{
  "url": "https://example.com/article",
  "formats": ["markdown", "html"],
  "wait_for_ms": 2000
}
```

### `POST /v1/crawl`
Crawl up to `limit` pages starting from `url`. The wrapper polls Firecrawl's
async job internally and returns the full result set (not a job ID).
```json
{
  "url": "https://docs.example.com",
  "max_depth": 2,
  "limit": 20,
  "formats": ["markdown"]
}
```

### `POST /v1/map`
Discover all URLs on a site without scraping content.
```json
{
  "url": "https://example.com",
  "limit": 500
}
```

### `POST /v1/extract` ⚠ Degraded — requires LLM provider
Extract structured data from a page using Firecrawl's LLM extraction.
```json
{
  "urls": ["https://example.com/products"],
  "prompt": "Extract product names and prices.",
  "schema_def": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "name":  { "type": "string" },
        "price": { "type": "string" }
      }
    }
  }
}
```

## Consumption (Python)

```python
import os
import requests

SCRAPER_URL = os.getenv("SCRAPER_URL", "https://scrape.platform.ibbytech.com")

def scrape_page(url: str, formats: list[str] | None = None) -> dict:
    """Scrape a single URL and return markdown/html content."""
    resp = requests.post(
        f"{SCRAPER_URL}/v1/scrape",
        json={"url": url, "formats": formats or ["markdown"]},
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["data"]


def map_site(url: str, limit: int = 500) -> list[str]:
    """Return a list of all URLs discovered on a site."""
    resp = requests.post(
        f"{SCRAPER_URL}/v1/map",
        json={"url": url, "limit": limit},
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["links"]


def crawl_site(url: str, max_depth: int = 2, limit: int = 20) -> list[dict]:
    """Crawl a site and return content from each page. Blocks until complete."""
    resp = requests.post(
        f"{SCRAPER_URL}/v1/crawl",
        json={"url": url, "max_depth": max_depth, "limit": limit, "formats": ["markdown"]},
        timeout=360,  # wrapper polls internally for up to 5 min
    )
    resp.raise_for_status()
    return resp.json()["data"]
```

## Observability
- **Loki Label:** Not yet configured — no structured log output from this service
- **Grafana Dashboard:** Not yet configured

⚠ Observability incomplete — Loki logging not yet implemented.

## Known Limitations / Quirks

1. **Extract is degraded:** `/v1/extract` requires `OPENAI_API_KEY` or `OLLAMA_BASE_URL`
   in `/opt/firecrawl/.env` on svcnode-01. Neither is currently set. The endpoint exists
   but Firecrawl will return an error when called. Fix: add the LLM provider key and run
   `docker compose restart` in `/opt/firecrawl/` on svcnode-01.

2. **Crawl timeout:** The wrapper polls Firecrawl's async crawl job for up to 5 minutes.
   Callers should set HTTP timeouts of at least 360 seconds when calling `/v1/crawl`.
   The scraper-api itself times out at 300 seconds internally; configure `limit` and
   `max_depth` accordingly to stay within that window.

3. **Firecrawl is LAN-only:** The Firecrawl backend (`svcnode-01:3002`) is not exposed
   through Traefik and has no TLS. Only the `scraper-api` wrapper is internet-accessible.
   Do not reference port 3002 from outside the LAN.

4. **No inbound authentication:** The scraper-api wrapper does not validate incoming
   requests. It is open to any caller that can reach `platform_net` or the Traefik FQDN.
   Add middleware auth before any external exposure.

5. **Self-hosted Firecrawl version:** Running `ghcr.io/mendableai/firecrawl:latest`.
   Crawl and extract API shapes may change on image updates. Pin to a digest in
   `/opt/firecrawl/docker-compose.yml` if stability is required.

6. **Firecrawl env must be maintained manually:** `/opt/firecrawl/.env` is root-owned
   on svcnode-01 and is not tracked in the platform repo. Required vars:
   `OPENAI_API_KEY`, `OPENAI_BASE_URL=https://api.openai.com/v1`.
   After any change, recreate containers with:
   `docker compose -f /opt/firecrawl/docker-compose.yaml --env-file /opt/firecrawl/.env --project-directory /opt/firecrawl up -d --force-recreate`
   (`docker restart` alone does not pick up `.env` changes — full recreate required.)

## Persistence & Semantic Search

Every API call automatically persists results and embeddings to `platform_v1`:

| Table | Endpoint | Embedding |
|:---|:---|:---|
| `scraper.scrape_results` | `/v1/scrape` | `embedding vector(1536)` + `embedding_json JSONB` |
| `scraper.crawl_results` | `/v1/crawl` | `embedding vector(1536)` + `embedding_json JSONB` |
| `scraper.map_results` | `/v1/map` | None (URL lists) |
| `scraper.extract_results` | `/v1/extract` | `embedding vector(1536)` + `embedding_json JSONB` |

HNSW cosine-similarity indexes on all embedding columns. Example query:
```sql
SELECT url, 1 - (embedding <=> '[0.1, 0.2, ...]'::vector) AS similarity
FROM scraper.scrape_results
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 10;
```
Embed queries via the LLM Gateway: `POST http://platform-llm-gateway:8080/v1/embeddings`

Schema files: `services/scraper/schema.sql` (base), `services/scraper/schema_embeddings.sql` (pgvector migration).

## Last Updated
2026-03-04 — All four endpoints fully validated. Extract working (Firecrawl
OPENAI_API_KEY + OPENAI_BASE_URL set). DB persistence + pgvector semantic search
confirmed across all tables. Service promoted from Degraded → Active.
