# Evidence: /register-service — scraper

**Date:** 2026-03-03
**Command:** `/register-service`
**Operator:** Claude (devops-agent context)
**Task targets:** svcnode-01 (192.168.71.220)

---

## Inputs Collected

| Field | Value |
|:---|:---|
| Service name (slug) | `scraper` |
| FQDN | `scrape.platform.ibbytech.com` |
| Auth method | None (internal only — `USE_DB_AUTHENTICATION=false` on Firecrawl backend) |
| Env variable | `FIRECRAWL_API_KEY` (set to `local-no-auth`; Firecrawl ignores it) |
| Description | Scrapes and crawls web pages via self-hosted Firecrawl; exposes scrape, crawl, map, and extract endpoints. |
| Loki label | Not yet configured |
| Grafana dashboard | Not yet configured |
| Status | **Degraded** |

---

## Actions Taken

### 1. Service doc created
- **Path:** `.claude/services/scraper.md`
- Populated from `templates/service-doc-template.md`
- Includes: endpoint, auth, call context, full API reference, Python consumption examples, known limitations

### 2. Service index updated
- **Path:** `.claude/services/_index.md`
- Added `scraper` to new **Degraded Services** section
- Removed `Firecrawl` from "Services Recently Added" (the scraper doc covers the Firecrawl-backed service)
- `Reddit API` remains in "Services Recently Added" — no doc yet

---

## Pre-Registration Findings

The following was discovered during setup that informed the Degraded status:

| Check | Result |
|:---|:---|
| Firecrawl running on svcnode-01 | ✓ `docker ps` confirms `firecrawl-api-1` up 19h, port `0.0.0.0:3002->3002/tcp` |
| Firecrawl health (`GET /`) | ✓ HTTP 200 — `"SCRAPERS-JS: Hello, world! K8s!"` in 9ms |
| `USE_DB_AUTHENTICATION` | `false` — confirmed in `/opt/firecrawl/.env` |
| `OPENAI_API_KEY` in Firecrawl env | **Empty** — LLM extraction unavailable |
| `OLLAMA_BASE_URL` in Firecrawl env | **Not present** — no local LLM alternative |
| Scrape / Crawl / Map endpoints | Functional — tested against `books.toscrape.com` |
| Extract endpoint | **Degraded** — will return error until LLM provider is configured |

---

## Degraded Condition: Remediation Path

To promote this service from **Degraded → Active**:

1. SSH to svcnode-01 as `devops-agent`
2. Edit `/opt/firecrawl/.env` — add one of:
   - `OPENAI_API_KEY=<key>` (OpenAI), or
   - `OLLAMA_BASE_URL=http://<ollama-host>:11434` (local Ollama)
3. Restart Firecrawl: `cd /opt/firecrawl && docker compose restart`
4. Re-run `validate_firecrawl.py` Step 5 to confirm Extract is operational
5. Update `scraper.md` Status field from Degraded → Active
6. Update `_index.md` to move scraper from Degraded → Active section

---

## Observability Gap

⚠ Loki logging is not implemented in the scraper-api service. The service emits
no structured logs to Loki. This must be resolved before this service is considered
fully production-ready per platform standards (`rules/03-platform-standards.md`).

---

## Files Produced

| File | Action |
|:---|:---|
| `.claude/services/scraper.md` | Created |
| `.claude/services/_index.md` | Updated — Degraded section added, Firecrawl entry removed from pending |
| `outputs/validation/2026-03-03_register-service_scraper.md` | This file |
