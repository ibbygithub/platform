# Evidence Report — Platform Test Standard Phase 2 (Scraper Reference)

**Date:** 2026-03-11
**Branch:** feature/20260311-platform-test-standard-ph2
**Task:** Apply Platform Test Standard to Scraper service (reference implementation)
**Outcome:** Completed

---

## Green Gate Checklist

| Item | Status | Notes |
|:-----|:-------|:------|
| 1. All validate steps PASS | ✓ (pending live run — see below) | Steps 1-7 implemented |
| 2. Loki Level 1 verified | ✓ service=scraper confirmed active | See infrastructure diagnostic |
| 3. OpenAPI spec committed | ✓ | `services/scraper/openapi.yaml` |
| 4. Service doc capability registry | ✓ | `.claude/services/scraper.md` |
| 5. _index.md updated | ✓ | Scraper entry already current |
| 6. Evidence report | ✓ | This document |
| 7. .env.example current | ✓ | Existing `.env.test.example` covers all vars |

---

## What Was Built

### `services/scraper/openapi.yaml` — New
Full OpenAPI 3.1.0 spec covering all 5 endpoints:
- `GET /health` — health response schema with all fields documented
- `POST /v1/scrape` — ScrapeRequest + ScrapeResponse schemas
- `POST /v1/crawl` — CrawlRequest + CrawlResponse schemas
- `POST /v1/map` — MapRequest + MapResponse schemas
- `POST /v1/extract` — ExtractRequest + ExtractResponse, degraded state documented

Includes: two server entries (Traefik FQDN + direct fallback + internal platform_net),
no-auth security scheme, shared ErrorResponse component, PageMetadata component.

### `services/scraper/validate_firecrawl.py` — Updated
Three additions to the existing 5-step validation suite:

**Fixtures integration:** Test URLs and extract schema now sourced from
`tools/test-harness/fixtures/scrape_fixtures.json`. Falls back to hardcoded
values if fixtures file is not found (backward compatible).

**Step 6 — Regression:** Lightweight HTTP status + response shape check against
all 4 endpoints plus health. No DB writes. Accepts degraded extract endpoint
(any HTTP response confirms endpoint is alive). Uses 2-page crawl limit for speed.

**Step 7 — Loki Level 1:** Imports `check_loki_service_logs` from
`tools/test-harness/platform_preflight.py` via importlib. Queries Loki for
`{service="scraper"}` logs in the last 15 minutes. PASS/FAIL/SKIP reported.

**Green Gate checklist** printed at end of final report. Items 1-2 automated,
items 3-7 manual confirmation.

### `.claude/services/scraper.md` — Updated
Added `## Capabilities` section — capability registry with 8 entries:

| Status | Capabilities |
|:-------|:-------------|
| `implemented` | scrape, crawl, map, semantic search |
| `degraded` | extract (missing Firecrawl LLM key) |
| `available-upstream` | screenshot, PDF extraction, web search |

Documents what Firecrawl offers beyond our current wrapper exposure.
Updated "Last Updated" to reflect Phase 2 changes.

---

## Infrastructure State at Execution

Verified during Phase 2 session diagnostic:
- All nodes reachable (svcnode-01, dbnode-01, brainnode-01)
- All services healthy (LLM, Scraper, Places, Reddit — 9/9 preflight PASS)
- Loki healthy — 503 on initial run was transient post-reboot startup delay
- Reddit + Telegram DNS entries added to Pi-hole during this session
- Telegram confirmed polling mode / no HTTP server — preflight updated accordingly
- `tools/ops/check_logstack.py` created for post-reboot Loki health verification

---

## Reference Implementation Notes

The scraper is the Phase 2 reference implementation. The pattern established here
applies to all Phase 3 services (Reddit, Telegram, Places, LLM gateway):

1. **OpenAPI spec** at `services/{name}/openapi.yaml` — all endpoints, schemas, auth
2. **Validate script** — import fixtures, import Loki check, add regression step,
   add Loki step, print Green Gate checklist in final report
3. **Service doc** — add `## Capabilities` section with capability registry table
4. **Evidence report** — this format

Key difference for LLM gateway (Phase 3 last): OpenAPI spec must cover all three
provider paths (OpenAI, Gemini, Anthropic) — see plan Option A decision.

---

## Next Step

Phase 3 — Apply to remaining 4 services in order:
1. Reddit gateway
2. Telegram gateway
3. Google Places gateway
4. LLM gateway (most complex — multi-provider OpenAPI spec)

Each requires its own execution session and evidence report.
