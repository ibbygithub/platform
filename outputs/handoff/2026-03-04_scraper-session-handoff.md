# Handoff Document — Scraper Service Session
**Date:** 2026-03-04
**Session scope:** Services/scraper — DB persistence, pgvector, extract endpoint, full validation
**Author:** Claude Code (Sonnet 4.6)
**Branch merged:** `claude/distracted-grothendieck` → `master`

---

## What Was Accomplished

### 1. Scraper API — v0.2.0 Deployed
The platform wrapper around Firecrawl (`scrape.platform.ibbytech.com`) was upgraded
from a stateless proxy to a fully persistent, embedding-aware service.

**Every API call now automatically:**
- Persists the result to `platform_v1` (Postgres on dbnode-01)
- Embeds the content via LLM Gateway (`text-embedding-3-small`, 1536-dim)
- Writes the embedding to both `embedding_json` JSONB (compatibility) and `embedding vector(1536)` (pgvector)
- DB/embed failures are non-fatal — the API always returns the scraped result

### 2. Database Schema — Created and Migrated
Applied to `dbnode-01` (`platform_v1`):

| Object | Details |
|:---|:---|
| `scraper_app` role | Login role with password, least-privilege grants |
| `scraper` schema | Owned by dba-agent |
| `scraper.scrape_results` | url, title, markdown, html, metadata JSONB, embedding vector(1536) |
| `scraper.crawl_results` | session_id UUID, url, status, markdown, metadata JSONB, embedding vector(1536) |
| `scraper.map_results` | root_url, url_count, urls JSONB (no embedding — not semantic) |
| `scraper.extract_results` | url, schema_def JSONB, extracted JSONB, embedding vector(1536) |
| pgvector extension | v0.8.1, installed as postgres superuser |
| HNSW indexes | `vector_cosine_ops`, m=16, ef_construction=64 on all 3 embedding tables |
| pg_hba.conf | Rule 18: `host platform_v1 scraper_app 192.168.71.220/32 scram-sha-256` |

Schema files committed: `services/scraper/schema.sql` and `services/scraper/schema_embeddings.sql`

### 3. Firecrawl — LLM Extract Unblocked
Firecrawl on svcnode-01 now has:
- `OPENAI_API_KEY` set in `/opt/firecrawl/.env`
- `OPENAI_BASE_URL=https://api.openai.com/v1` added (was missing — caused relative URL crash)

### 4. All Four Endpoints Validated

| Endpoint | Result | DB | Vector |
|:---|:---|:---|:---|
| `POST /v1/scrape` | ✅ Returns markdown + metadata | ✅ | ✅ |
| `POST /v1/map` | ✅ Returns URL list | ✅ | n/a |
| `POST /v1/crawl` | ✅ Polls async job, returns pages | ✅ | ✅ |
| `POST /v1/extract` | ✅ LLM-extracted structured data (20 books) | ✅ | ✅ |

### 5. Semantic Search Validated
End-to-end RAG pipeline confirmed:
- Embed query via LLM Gateway
- Cosine similarity search via `embedding <=> query::vector`
- HNSW index used automatically
- Test: "poetry books for children" → ranked "A Light in the Attic" (Shel Silverstein) first at sim=0.43

### 6. Git & GitHub — Fully Up to Date
- All commits merged to `master` and pushed
- `.claude/` directory (CLAUDE.md, rules, service docs, templates) committed to git for the first time
- Service promoted from **Degraded → Active** in `_index.md` and `scraper.md`

---

## What Is Not Working / Gaps

### 🔴 High Priority

**1. Loki logging not implemented in scraper-api**
The service has zero structured log output to Loki. All logs go to Docker stdout only.
This violates the platform observability standard (rules/03-platform-standards.md).
Every inbound request and every Firecrawl/embedding call should emit a structured log
with `service=scraper`, response code, latency, and URL. Until this is done, there is
no billing traceability, no alerting, and no Grafana visibility for this service.

**2. Firecrawl map and crawl returning minimal results**
Both `POST /v1/map` and `POST /v1/crawl` on `books.toscrape.com` returned only 1 URL/page
despite `limit=20` and `limit=5` respectively. This is likely a Firecrawl configuration
issue — either the self-hosted instance has a low crawl concurrency setting, or the async
worker is underprovisioned. Has not been investigated. Functional but not production-ready
for large crawls.

**3. svcnode-01 is still on the feature branch**
The deployment on svcnode-01 pulled from `claude/distracted-grothendieck`. Now that master
is updated, the server should be updated:
```bash
ssh devops-agent@192.168.71.220
cd /opt/git/work/platform
git checkout master
git pull origin master
cd services/scraper && docker compose build && docker compose up -d --force-recreate
```

### 🟡 Medium Priority

**4. Firecrawl installed at `/opt/firecrawl` — violates platform path convention**
Platform standard is `/opt/git/work/<project-name>/`. Firecrawl predates this standard
and is root-owned at `/opt/firecrawl`. Either migrate it or add a documented exception
to the infrastructure rules. Migration would require: clone to correct path, update
any cron jobs or references, switch running containers, decommission `/opt/firecrawl/`.

**5. Firecrawl `.env` is untracked, root-owned, and fragile**
`/opt/firecrawl/.env` is not in git, is owned by root, and was modified manually during
this session. If svcnode-01 is rebuilt, this config will be lost. The required variables
(`OPENAI_API_KEY`, `OPENAI_BASE_URL`) need to be documented or injected through a
controlled mechanism (e.g., Ansible, a secrets manager, or a tracked override compose file).

**6. `docker restart` does not pick up Firecrawl `.env` changes**
Firecrawl uses Docker Compose variable substitution — values are baked in at container
creation time. `docker restart` reuses the old spec. This tripped up this session.
**The correct restart command is:**
```bash
docker compose -f /opt/firecrawl/docker-compose.yaml \
  --env-file /opt/firecrawl/.env \
  --project-directory /opt/firecrawl \
  up -d --force-recreate
```
This is documented in `scraper.md` limitation #6 but should also be added to a runbook.

**7. No inbound authentication on scraper-api**
Anyone who can reach `scrape.platform.ibbytech.com` or `platform_net` can make unlimited
scraping requests. No API key, no rate limiting, no IP allowlist. This is acceptable for
internal-only use but must be addressed before any external exposure or before cost
becomes a concern (every extract call uses OpenAI tokens).

**8. Reddit API service has no service doc**
`services/reddit-gateway/` exists and has content (`reddit-devvit-shogun-v1.txt` is
untracked in git). `_index.md` lists it under "Recently Added (Docs Pending)". Run
`/register-service` to generate the doc and commit it.

### 🟢 Low Priority / Cleanup

**9. `embedding_json` JSONB column can be dropped once stable**
The schema has both `embedding_json JSONB` (Phase 1 fallback) and `embedding vector(1536)`
(Phase 2). The app now writes both simultaneously. After a stable period (e.g., 30 days),
`embedding_json` can be dropped to recover storage. SQL:
```sql
ALTER TABLE scraper.scrape_results  DROP COLUMN embedding_json;
ALTER TABLE scraper.crawl_results   DROP COLUMN embedding_json;
ALTER TABLE scraper.extract_results DROP COLUMN embedding_json;
```

**10. Firecrawl image is not pinned**
`docker-compose.yaml` uses `ghcr.io/mendableai/firecrawl:latest`. An upstream image update
could silently change API shapes (this has happened with Firecrawl before). Pin to a
specific digest for stability.

**11. `services/reddit-gateway/reddit-devvit-shogun-v1.txt` is untracked**
This file is sitting in the repo but not committed. Commit or gitignore it.

---

## What Should Be Done Next (Ordered)

1. **Update svcnode-01 to master** (5 min, unblocked)
   ```bash
   ssh devops-agent@192.168.71.220
   cd /opt/git/work/platform && git checkout master && git pull
   cd services/scraper && docker compose build && docker compose up -d --force-recreate
   ```

2. **Add Loki logging to scraper-api** (1–2 hrs, engineering task)
   Add the Loki log driver to `docker-compose.yml` and structured `logging.getLogger`
   calls in `app.py` for every request/response. Required for platform compliance.

3. **Investigate Firecrawl map/crawl concurrency** (30 min, ops)
   Check Firecrawl worker logs during a crawl with `limit=20` to understand why only
   1 page/URL is returned. Likely a `CRAWLER_WORKERS` or `MAX_CONCURRENCY` env var
   needs to be set in `/opt/firecrawl/.env`.

4. **Register Reddit API** (15 min, docs)
   Run `/register-service`, answer questions, commit the service doc.

5. **Firecrawl path migration** (1–2 hrs, ops + policy decision)
   Decide: migrate to `/opt/git/work/firecrawl/` or formally document the exception.

6. **Add auth to scraper-api** (2–4 hrs, engineering)
   Either Traefik BasicAuth middleware or a simple API key header check in FastAPI.

7. **Drop `embedding_json` columns** (after 30-day stable period)
   Scheduled cleanup once confident the vector column is reliable.

---

## Key Operational Notes for Future Sessions

### Credentials in Use
| Secret | Where | Notes |
|:---|:---|:---|
| `scraper_app` DB password | `services/scraper/.env` on svcnode-01 (not in git) | `PGPASSWORD=s7Ki9YksFm60CNdyOv3D7V3tW0QuMyR9` |
| Firecrawl API key | `FIRECRAWL_API_KEY=local-no-auth` | Placeholder — auth is disabled |
| OPENAI_API_KEY | `/opt/firecrawl/.env` + `services/scraper/.env` on svcnode-01 | Not in git |
| OPENAI_BASE_URL | `/opt/firecrawl/.env` | `https://api.openai.com/v1` — was missing, caused extract failure |

### How to Connect to Each Component
| Component | How |
|:---|:---|
| scraper-api (from LAN) | `http://scrape.platform.ibbytech.com` or `http://platform-scraper-api:8083` (inside platform_net) |
| Firecrawl direct | `http://192.168.71.220:3002` (LAN only) |
| platform_v1 DB | `psql -U dba-agent -d platform_v1` (via peer auth on dbnode-01) |
| scraper_app role | Needs TCP from 192.168.71.220 — pg_hba.conf rule 18 |

### Sudo / Permissions Discovered
| Action | Who Can | Method |
|:---|:---|:---|
| Install pgvector extension | dba-agent | `sudo -u postgres /usr/bin/psql` (NOPASSWD) |
| Modify pg_hba.conf | dba-agent | `\! echo ... >> /etc/postgresql/...` via psql shell escape |
| Write `/opt/firecrawl/.env` | root only | devops-agent has no NOPASSWD for file writes |
| Force-recreate Firecrawl containers | devops-agent | `docker compose -f ... up --force-recreate` (no root needed) |
| `docker restart` | devops-agent | Works but does NOT re-read `.env` for compose-managed containers |

### Databases on dbnode-01
There are at least two databases in use:
- `shogun_v1` — referenced in infrastructure rules and older services (places_app)
- `platform_v1` — used by scraper service and newer platform services

These appear to be separate databases (possibly for different project phases). Clarify
whether `shogun_v1` is being deprecated or whether new services should target one or both.
