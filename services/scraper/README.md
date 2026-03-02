# Scraper

Web scraping and crawling service. A thin FastAPI wrapper (`scraper-api`) sits in front of a self-hosted Firecrawl instance, exposing a clean platform-consistent API.

## Endpoints

| FQDN | Purpose |
|------|---------|
| `scrape.platform.ibbytech.com` | Web scraping and crawling |

## Architecture

```
Caller → scraper-api (platform_net) → firecrawl-api (scraper_internal)
                                     ← firecrawl-worker
                                     ← scraper-redis
```

Only `scraper-api` is exposed to Traefik. Firecrawl and Redis are on an isolated internal network.

## Quick Start

```bash
cp .env.example .env    # set FIRECRAWL_API_KEY to any string you choose
docker compose up --build -d
curl https://scrape.platform.ibbytech.com/health
```

## API

### `GET /health`
Reports whether Firecrawl is reachable internally.
```json
{ "ok": true, "firecrawl_reachable": true }
```

### `POST /v1/scrape`
Scrape a single URL. Returns markdown content and page metadata.
```json
{
  "url": "https://example.com/article",
  "formats": ["markdown"],
  "wait_for_ms": 2000
}
```

### `POST /v1/crawl`
Crawl a site up to `max_depth` levels, returning up to `limit` pages.
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
  "limit": 100
}
```

## Firecrawl Notes

- Self-hosted image: `ghcr.io/mendableai/firecrawl:latest`
- Check https://github.com/mendableai/firecrawl for the latest self-hosted setup notes
- `OPENAI_API_KEY` in `.env` is optional — only needed for Firecrawl's LLM-based structured extraction
- JavaScript rendering is handled by Firecrawl internally; use `wait_for_ms` for JS-heavy pages
