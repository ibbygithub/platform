# Scraper Service — Consumer Guide

**For:** Developers and AI agents building applications that need web content retrieval,
structured data extraction, or semantic search over scraped content.

**Service URL:** `https://scrape.platform.ibbytech.com`
**Internal URL (platform_net containers):** `http://platform-scraper-api:8083`
**Auth:** None required — open on the internal network
**Full service doc:** [scraper.md](scraper.md)

---

## When to Use This Service

| You need to... | Use |
|:---|:---|
| Get the text/markdown content of a web page | `POST /v1/scrape` |
| Discover all URLs on a site | `POST /v1/map` |
| Retrieve content from multiple pages of a site | `POST /v1/crawl` |
| Pull structured data (prices, names, fields) from a page via LLM | `POST /v1/extract` |
| Search previously scraped content semantically | Query `platform_v1` directly via pgvector |

**Do not** use raw `requests`/`fetch` to scrape sites yourself. This service handles
JavaScript rendering, async job polling, result persistence, and embedding automatically.

---

## Quick Reference

```
POST /v1/scrape    → single URL → markdown + metadata + embedding persisted
POST /v1/crawl     → site crawl → N pages → each page persisted with embedding
POST /v1/map       → site map   → list of URLs → persisted (no embedding)
POST /v1/extract   → LLM extraction → structured JSON → persisted with embedding
GET  /health       → service status check
```

Every successful call:
1. Returns the result immediately to the caller
2. Persists to `platform_v1` on dbnode-01 (non-blocking, non-fatal)
3. Generates an OpenAI `text-embedding-3-small` vector (1536-dim) and stores it

---

## Endpoint Reference

### GET /health

Check whether all components are reachable.

**curl:**
```bash
curl https://scrape.platform.ibbytech.com/health
```

**Expected response:**
```json
{
  "ok": true,
  "time": 1741000000,
  "firecrawl_reachable": true,
  "db_connected": true,
  "persist_enabled": true,
  "embed_provider": "openai",
  "embed_model": "text-embedding-3-small"
}
```

If `firecrawl_reachable` is `false`, scraping will fail. If `db_connected` is `false`,
scraping still works but results will not be persisted.

---

### POST /v1/scrape

Scrape a single URL. Returns markdown, HTML, and page metadata.
Results are auto-persisted to `scraper.scrape_results`.

**Request body:**
```json
{
  "url": "https://example.com/article",
  "formats": ["markdown"],
  "include_tags": ["article", "main"],
  "exclude_tags": ["nav", "footer"],
  "wait_for_ms": 2000
}
```

| Field | Type | Default | Notes |
|:---|:---|:---|:---|
| `url` | string | required | Full URL including scheme |
| `formats` | string[] | `["markdown"]` | Options: `"markdown"`, `"html"` |
| `include_tags` | string[] | null | Only extract these HTML tags |
| `exclude_tags` | string[] | null | Strip these HTML tags from output |
| `wait_for_ms` | int | null | Wait N ms for JS to render before scraping |

**curl:**
```bash
curl -X POST https://scrape.platform.ibbytech.com/v1/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://news.ycombinator.com", "formats": ["markdown"]}'
```

**Python:**
```python
import requests

SCRAPER_URL = "https://scrape.platform.ibbytech.com"

def scrape(url: str, formats: list[str] = None, wait_ms: int = None) -> dict:
    payload = {"url": url, "formats": formats or ["markdown"]}
    if wait_ms:
        payload["wait_for_ms"] = wait_ms
    resp = requests.post(f"{SCRAPER_URL}/v1/scrape", json=payload, timeout=90)
    resp.raise_for_status()
    return resp.json()["data"]   # keys: markdown, html, metadata

result = scrape("https://news.ycombinator.com")
print(result["markdown"][:500])
print(result["metadata"]["title"])
```

**JavaScript/TypeScript:**
```typescript
const SCRAPER_URL = "https://scrape.platform.ibbytech.com";

async function scrape(url: string, formats = ["markdown"]): Promise<Record<string, any>> {
  const res = await fetch(`${SCRAPER_URL}/v1/scrape`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, formats }),
    signal: AbortSignal.timeout(90_000),
  });
  if (!res.ok) throw new Error(`Scrape failed: ${res.status} ${await res.text()}`);
  const body = await res.json();
  return body.data;  // { markdown, html, metadata }
}

const data = await scrape("https://news.ycombinator.com");
console.log(data.markdown.slice(0, 500));
```

**Response shape:**
```json
{
  "ok": true,
  "url": "https://news.ycombinator.com",
  "data": {
    "markdown": "# Hacker News\n...",
    "html": "<html>...</html>",
    "metadata": {
      "title": "Hacker News",
      "description": "...",
      "sourceURL": "https://news.ycombinator.com",
      "statusCode": 200
    }
  }
}
```

---

### POST /v1/map

Discover all URLs on a site without fetching page content.
Results are auto-persisted to `scraper.map_results`.

**Request body:**
```json
{
  "url": "https://docs.example.com",
  "limit": 500
}
```

| Field | Type | Default | Range |
|:---|:---|:---|:---|
| `url` | string | required | Root URL to map |
| `limit` | int | `50` | 1–500 |

**curl:**
```bash
curl -X POST https://scrape.platform.ibbytech.com/v1/map \
  -H "Content-Type: application/json" \
  -d '{"url": "https://docs.example.com", "limit": 100}'
```

**Python:**
```python
def map_site(url: str, limit: int = 100) -> list[str]:
    resp = requests.post(f"{SCRAPER_URL}/v1/map",
                         json={"url": url, "limit": limit}, timeout=90)
    resp.raise_for_status()
    return resp.json()["links"]   # list of URL strings

urls = map_site("https://docs.example.com")
print(f"Found {len(urls)} URLs")
```

**JavaScript/TypeScript:**
```typescript
async function mapSite(url: string, limit = 100): Promise<string[]> {
  const res = await fetch(`${SCRAPER_URL}/v1/map`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, limit }),
    signal: AbortSignal.timeout(90_000),
  });
  if (!res.ok) throw new Error(`Map failed: ${res.status}`);
  return (await res.json()).links;
}
```

**Response shape:**
```json
{
  "ok": true,
  "url": "https://docs.example.com",
  "links": [
    "https://docs.example.com/",
    "https://docs.example.com/getting-started",
    "https://docs.example.com/api-reference"
  ]
}
```

---

### POST /v1/crawl

Crawl a site and return content from multiple pages. The wrapper polls Firecrawl's
async job internally and blocks until complete (up to 5 minutes).
Each page is persisted to `scraper.crawl_results` with a shared `session_id`.

**Request body:**
```json
{
  "url": "https://docs.example.com",
  "max_depth": 2,
  "limit": 20,
  "formats": ["markdown"]
}
```

| Field | Type | Default | Range |
|:---|:---|:---|:---|
| `url` | string | required | Root URL to crawl from |
| `max_depth` | int | `2` | 1–10 |
| `limit` | int | `10` | 1–100 |
| `formats` | string[] | `["markdown"]` | `"markdown"`, `"html"` |

**⚠ Set your HTTP client timeout to at least 360 seconds** — crawl jobs can take up to 5 minutes.

**curl:**
```bash
curl -X POST https://scrape.platform.ibbytech.com/v1/crawl \
  -H "Content-Type: application/json" \
  --max-time 360 \
  -d '{"url": "https://docs.example.com", "max_depth": 2, "limit": 10}'
```

**Python:**
```python
def crawl(url: str, max_depth: int = 2, limit: int = 10) -> dict:
    resp = requests.post(
        f"{SCRAPER_URL}/v1/crawl",
        json={"url": url, "max_depth": max_depth, "limit": limit,
              "formats": ["markdown"]},
        timeout=360,   # must be >= 300
    )
    resp.raise_for_status()
    result = resp.json()
    return result   # keys: ok, url, session_id, total, data

result = crawl("https://docs.example.com", max_depth=2, limit=10)
print(f"session_id: {result['session_id']}")
print(f"pages crawled: {result['total']}")
for page in result["data"]:
    url = (page.get("metadata") or {}).get("sourceURL", "")
    print(f"  {url}: {len(page.get('markdown', ''))} chars")
```

**JavaScript/TypeScript:**
```typescript
async function crawl(url: string, maxDepth = 2, limit = 10) {
  const res = await fetch(`${SCRAPER_URL}/v1/crawl`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, max_depth: maxDepth, limit, formats: ["markdown"] }),
    signal: AbortSignal.timeout(360_000),
  });
  if (!res.ok) throw new Error(`Crawl failed: ${res.status}`);
  return await res.json();  // { ok, url, session_id, total, data[] }
}

const result = await crawl("https://docs.example.com");
console.log(`Session: ${result.session_id}, Pages: ${result.total}`);
```

**Response shape:**
```json
{
  "ok": true,
  "url": "https://docs.example.com",
  "session_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "total": 8,
  "data": [
    {
      "markdown": "# Getting Started\n...",
      "metadata": {
        "sourceURL": "https://docs.example.com/getting-started",
        "statusCode": 200
      }
    }
  ]
}
```

> **Tip:** Save the `session_id`. You can use it later to query all pages from this
> crawl in Postgres: `SELECT * FROM scraper.crawl_results WHERE session_id = '...'`

---

### POST /v1/extract

Use an LLM to extract structured data from one or more URLs. Firecrawl scrapes the
pages and passes them to OpenAI to fill a JSON schema.
Results are persisted to `scraper.extract_results`.

**Request body:**
```json
{
  "urls": ["https://example.com/products"],
  "prompt": "Extract all product names and prices.",
  "schema_def": {
    "type": "object",
    "properties": {
      "products": {
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
  }
}
```

| Field | Type | Default | Notes |
|:---|:---|:---|:---|
| `urls` | string[] | required | One or more URLs to extract from |
| `prompt` | string | null | Natural language instruction for the LLM |
| `schema_def` | object | null | JSON Schema for the output structure |

**curl:**
```bash
curl -X POST https://scrape.platform.ibbytech.com/v1/extract \
  -H "Content-Type: application/json" \
  --max-time 180 \
  -d '{
    "urls": ["https://example.com/team"],
    "prompt": "Extract the names and titles of all team members."
  }'
```

**Python:**
```python
def extract(urls: list[str], prompt: str, schema: dict = None) -> dict:
    payload = {"urls": urls, "prompt": prompt}
    if schema:
        payload["schema_def"] = schema
    resp = requests.post(f"{SCRAPER_URL}/v1/extract",
                         json=payload, timeout=180)
    resp.raise_for_status()
    return resp.json()["data"]   # structured data matching your schema

schema = {
    "type": "object",
    "properties": {
        "team": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name":  {"type": "string"},
                    "title": {"type": "string"}
                }
            }
        }
    }
}
data = extract(["https://example.com/team"],
               prompt="Extract all team members with their titles.",
               schema=schema)
for person in data.get("team", []):
    print(person["name"], "—", person["title"])
```

**JavaScript/TypeScript:**
```typescript
async function extract(
  urls: string[],
  prompt: string,
  schemaDef?: Record<string, any>
) {
  const res = await fetch(`${SCRAPER_URL}/v1/extract`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ urls, prompt, schema_def: schemaDef }),
    signal: AbortSignal.timeout(180_000),
  });
  if (!res.ok) throw new Error(`Extract failed: ${res.status}`);
  return (await res.json()).data;
}
```

**Response shape:**
```json
{
  "ok": true,
  "urls": ["https://example.com/team"],
  "data": {
    "team": [
      { "name": "Jane Smith", "title": "CEO" },
      { "name": "John Doe",   "title": "CTO" }
    ]
  }
}
```

---

## Error Handling

All errors return HTTP 4xx/5xx with a JSON body.

| Status | Meaning | Action |
|:---|:---|:---|
| `502` source=`firecrawl` | Firecrawl engine error | Check Firecrawl health; retry once |
| `502` source=`firecrawl_poll` | Crawl job polling error | Retry with smaller `limit` |
| `504` | Crawl/extract job timed out | Reduce `limit` or `max_depth` |
| `500` | Internal error in scraper-api | Check service logs |
| `422` | Invalid request body | Check required fields and types |

**Python error handling:**
```python
from requests.exceptions import HTTPError, Timeout

try:
    result = scrape("https://example.com")
except Timeout:
    print("Request timed out — increase timeout or try again")
except HTTPError as e:
    if e.response.status_code == 502:
        detail = e.response.json().get("detail", {})
        print(f"Firecrawl error: {detail}")
    elif e.response.status_code == 504:
        print("Job timed out — reduce crawl limit")
    else:
        raise
```

**Note on DB/embed failures:** If Postgres or the LLM Gateway is unavailable, the API
still returns the scraped content — persistence and embedding are non-fatal side-effects.
The response will be successful even if no row was written to the database.

---

## Full RAG Pipeline — Semantic Search Over Scraped Content

Use this pattern to build knowledge bases that can be searched by meaning rather than
keywords. All scraped content is automatically embedded and indexed; you only need to
embed the query and run the similarity search.

### Step 1 — Populate the Knowledge Base

Scrape, crawl, or extract the content you want to search. It is stored automatically.

```python
# Crawl a documentation site
result = crawl("https://docs.yourapp.com", max_depth=3, limit=50)
print(f"Indexed {result['total']} pages (session: {result['session_id']})")
```

### Step 2 — Embed the Query

Call the LLM Gateway embedding endpoint with your search query.

**Python:**
```python
import requests

LLM_GATEWAY = "http://platform-llm-gateway:8080"  # inside platform_net
# Or use the external URL if calling from outside: https://llm.platform.ibbytech.com

def embed(text: str) -> list[float]:
    resp = requests.post(
        f"{LLM_GATEWAY}/v1/embeddings",
        json={
            "provider": "openai",
            "model":    "text-embedding-3-small",
            "input":    [text],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["vectors"][0]   # list of 1536 floats

query_vector = embed("how do I reset my password?")
```

**JavaScript/TypeScript:**
```typescript
const LLM_GATEWAY = "http://platform-llm-gateway:8080";

async function embed(text: string): Promise<number[]> {
  const res = await fetch(`${LLM_GATEWAY}/v1/embeddings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      provider: "openai",
      model: "text-embedding-3-small",
      input: [text],
    }),
  });
  const body = await res.json();
  return body.vectors[0];
}

const queryVector = await embed("how do I reset my password?");
```

### Step 3 — Search with Cosine Similarity

Connect to `platform_v1` on dbnode-01 and run a vector similarity search.

**Python (psycopg2):**
```python
import json
import psycopg2

PG_CONFIG = {
    "host":     "192.168.71.221",   # dbnode-01
    "port":     5432,
    "dbname":   "platform_v1",
    "user":     "scraper_app",
    "password": "<PGPASSWORD>",     # from services/scraper/.env
}

def semantic_search(
    query: str,
    table: str = "scrape_results",   # or "crawl_results", "extract_results"
    top_k: int = 5,
    session_id: str = None,          # optional: filter to one crawl session
) -> list[dict]:
    query_vector = json.dumps(embed(query))
    sql = f"""
        SELECT url,
               1 - (embedding <=> %s::vector) AS similarity,
               LEFT(markdown, 500)             AS preview
        FROM   scraper.{table}
        WHERE  embedding IS NOT NULL
        {"AND session_id = %s" if session_id else ""}
        ORDER BY embedding <=> %s::vector
        LIMIT  %s
    """
    params = [query_vector, query_vector, top_k]
    if session_id:
        params = [query_vector, session_id, query_vector, top_k]

    conn = psycopg2.connect(**PG_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()

# Example usage
results = semantic_search("password reset instructions", table="crawl_results", top_k=3)
for r in results:
    print(f"sim={r['similarity']:.4f}  {r['url']}")
    print(f"  {r['preview'][:200]}\n")
```

**Raw SQL (for any Postgres client):**
```sql
-- Embed your query first, then paste the vector here
SELECT
    url,
    1 - (embedding <=> '[0.021, -0.043, ...]'::vector) AS similarity,
    LEFT(markdown, 300) AS preview
FROM scraper.scrape_results
WHERE embedding IS NOT NULL
ORDER BY embedding <=> '[0.021, -0.043, ...]'::vector
LIMIT 5;

-- Filter to a specific crawl session:
SELECT url, 1 - (embedding <=> '[...]'::vector) AS similarity
FROM scraper.crawl_results
WHERE embedding IS NOT NULL
  AND session_id = 'f47ac10b-58cc-4372-a567-0e02b2c3d479'
ORDER BY embedding <=> '[...]'::vector
LIMIT 5;
```

### Which Table to Search?

| Table | Best for |
|:---|:---|
| `scraper.scrape_results` | Known URLs you scraped individually |
| `scraper.crawl_results` | Site-wide crawl knowledge bases (filter by `session_id`) |
| `scraper.extract_results` | Structured extracted data (the embedded text is the JSON output) |

---

## Recommended Patterns

### Pattern 1 — One-off page fetch (most common)
```python
data = scrape("https://example.com/docs/api")
content = data["markdown"]
# use content in your prompt or processing pipeline
```

### Pattern 2 — Build a searchable site knowledge base
```python
# 1. Index the site (do this once or on a schedule)
result = crawl("https://docs.yourapp.com", max_depth=3, limit=100)
session_id = result["session_id"]

# 2. Answer user questions using semantic search
hits = semantic_search(user_question, table="crawl_results",
                       session_id=session_id, top_k=3)
context = "\n\n".join(h["preview"] for h in hits)
# Pass context to your LLM for a grounded answer
```

### Pattern 3 — Extract and store structured data at scale
```python
urls = map_site("https://ecommerce.example.com/products", limit=200)

schema = {"type": "object", "properties": {
    "name":     {"type": "string"},
    "price":    {"type": "string"},
    "in_stock": {"type": "boolean"},
}}

for url in urls:
    try:
        data = extract([url], prompt="Extract product details.", schema=schema)
        # data is auto-persisted; use it directly or query later via pgvector
    except Exception as e:
        print(f"Failed {url}: {e}")
```

---

## Timeouts — Quick Reference

| Endpoint | Recommended client timeout |
|:---|:---|
| `/v1/scrape` | 90 seconds |
| `/v1/map` | 90 seconds |
| `/v1/crawl` | **360 seconds** (job can run up to 5 min internally) |
| `/v1/extract` | 180 seconds |

---

## For AI Agents

When deciding which endpoint to use, follow this decision tree:

1. **Do you have a single specific URL?** → `/v1/scrape`
2. **Do you need to discover what pages exist on a site?** → `/v1/map`
3. **Do you need content from many pages of a site?** → `/v1/crawl` (set `limit` conservatively — start with 10)
4. **Do you need structured fields (prices, names, dates) from a page?** → `/v1/extract`
5. **Do you need to answer a question using content already scraped?** → embed the question via LLM Gateway, query `scraper.*` tables via pgvector

**Agent rules:**
- Always check `/health` before starting a multi-step scraping workflow
- Use `session_id` from crawl results to scope semantic searches to the right dataset
- If a scrape returns `ok: true` but `markdown` is empty, the page may require JavaScript rendering — retry with `"wait_for_ms": 3000`
- Treat DB write failures as non-fatal — the API response is still valid even if persistence failed
- Never call Firecrawl at `http://192.168.71.220:3002` directly — always go through the platform wrapper
