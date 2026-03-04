# Scraper Service Validation Report
**Date:** 2026-03-04
**Branch:** `claude/distracted-grothendieck`
**Node:** svcnode-01 (192.168.71.220) — Docker deployment
**DB Node:** dbnode-01 (192.168.71.221) — platform_v1

---

## Executive Summary

The scraper-api service (`scrape.platform.ibbytech.com`) has been fully deployed and validated for:
- Firecrawl connectivity (scrape, map, crawl endpoints)
- PostgreSQL persistence (all 4 tables in `scraper` schema)
- OpenAI embeddings via LLM Gateway (`text-embedding-3-small`, 1536-dim)
- pgvector semantic similarity search with HNSW indexes

**Extract** endpoint remains blocked pending root-level action on svcnode-01 (Firecrawl OPENAI_API_KEY not set).

---

## Infrastructure Completed This Session

### DB Schema (dbnode-01)
| Object | Status |
|:---|:---|
| `scraper_app` role + password | ✅ Created |
| `scraper` schema | ✅ Created |
| `scraper.scrape_results` table | ✅ Created |
| `scraper.map_results` table | ✅ Created |
| `scraper.crawl_results` table + session index | ✅ Created |
| `scraper.extract_results` table | ✅ Created |
| `embedding_json JSONB` column (all 3 applicable tables) | ✅ Added |
| pgvector extension | ✅ Installed (v0.8.1) |
| `embedding vector(1536)` column (all 3 applicable tables) | ✅ Added |
| HNSW indexes (`vector_cosine_ops`, m=16, ef=64) | ✅ Created (3 indexes) |
| pg_hba.conf entry for scraper_app from svcnode-01 | ✅ Added (rule 18, line 34) |

### Code Changes (committed to branch)
| File | Change |
|:---|:---|
| `services/scraper/api/app.py` | Rewritten v0.2.0 — DB persist + embed on every call |
| `services/scraper/api/requirements.txt` | Added `psycopg2-binary==2.9.10` |
| `services/scraper/docker-compose.yml` | Added `LLM_GATEWAY_URL`; `dbnode-01` in `extra_hosts` |
| `services/scraper/schema.sql` | New — base table definitions |
| `services/scraper/schema_embeddings.sql` | New — pgvector migration |

Commits:
- `d4346cf` — feat(scraper): auto-persist + embed all scrape results to Postgres
- `4c14b92` — fix(scraper): write pgvector embedding column directly on insert; add dbnode-01 extra_hosts

---

## Test Results

### Health Check
```json
{
  "ok": true,
  "firecrawl_reachable": true,
  "db_connected": true,
  "persist_enabled": true,
  "embed_provider": "openai",
  "embed_model": "text-embedding-3-small"
}
```

### T-5: Functional Write Tests

| Test | URL | Result | DB Row | embedding_json | embedding (vector) |
|:---|:---|:---|:---|:---|:---|
| `/v1/scrape` | books.toscrape.com | ✅ ok=True, md_len=9222 | ✅ row inserted | ✅ 1536-dim | ✅ vector(1536) |
| `/v1/scrape` | book detail page | ✅ ok=True, md_len=1913 | ✅ row inserted | ✅ 1536-dim | ✅ vector(1536) |
| `/v1/map` | books.toscrape.com | ✅ ok=True, 1 link | ✅ row inserted | n/a | n/a |
| `/v1/crawl` | books.toscrape.com | ✅ ok=True, 1 page, session_id set | ✅ row inserted | ✅ 1536-dim | ✅ vector(1536) |
| `/v1/extract` | books.toscrape.com | ❌ Firecrawl 500 | no row | — | — |

**Extract blocked reason:** Firecrawl `/opt/firecrawl/.env` has `OPENAI_API_KEY=` (empty).
Fix requires root on svcnode-01: `sudo sed -i "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=<key>|" /opt/firecrawl/.env && cd /opt/firecrawl && docker compose restart`

### T-6: Semantic Search Test

Query: `"poetry books for children"`
Embedding API: `POST http://platform-llm-gateway:8080/v1/embeddings` → 200, 1536-dim
Search: `embedding <=> query::vector` cosine distance, HNSW index used

| Rank | Similarity | URL |
|:---|:---|:---|
| 1 | 0.4320 | `books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html` |
| 2 | 0.3144 | `books.toscrape.com` |

✅ **Correct** — "A Light in the Attic" (Shel Silverstein poetry book) ranked above the generic catalog page.

---

## DB Row Counts (end of session)

```sql
 scrape_results  | rows=2 | embedding_json=2 | vector=2
 map_results     | rows=1
 crawl_results   | rows=1 | embedding_json=1 | vector=1
 extract_results | rows=0
```

---

## Open Items (require root/superuser action)

| # | Item | Node | Action Required |
|:---|:---|:---|:---|
| 1 | Firecrawl OPENAI_API_KEY | svcnode-01 | `sudo sed -i "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=<key>|" /opt/firecrawl/.env && cd /opt/firecrawl && docker compose restart` |
| 2 | Loki logging | svcnode-01 | Add Loki log driver to scraper-api container in docker-compose.yml |

---

## Validated Architecture

```
ibbytech-laptop
    └── git push → GitHub → git pull → svcnode-01
                                           │
                   ┌───────────────────────┤
                   │   platform-scraper-api (port 8083)
                   │       │  ↓ scrape/crawl/map/extract
                   │       │  http://host.docker.internal:3002
                   │       │       └─ Firecrawl (self-hosted, /opt/firecrawl)
                   │       │
                   │       │  ↓ embed text
                   │       │  http://platform-llm-gateway:8080/v1/embeddings
                   │       │       └─ LLM Gateway → OpenAI text-embedding-3-small
                   │       │
                   │       │  ↓ persist results + vectors
                   │       └─ dbnode-01:5432/platform_v1
                   │              scraper.scrape_results  (HNSW index)
                   │              scraper.crawl_results   (HNSW index)
                   │              scraper.map_results
                   │              scraper.extract_results (HNSW index)
                   │
                   └── Traefik → scrape.platform.ibbytech.com
```
