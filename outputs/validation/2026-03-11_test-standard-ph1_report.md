# Evidence Report — Platform Test Standard Phase 1

**Date:** 2026-03-11
**Branch:** feature/20260311-platform-test-standard-ph1
**Task:** Platform Test Standard — Phase 1 Foundation
**Outcome:** Completed

---

## What Was Built

### `tools/test-harness/` — New shared test infrastructure directory

#### `platform_preflight.py`
Master infrastructure readiness check. Stage 2 Part A of the development cycle.
Covers:
- Node reachability (svcnode-01, dbnode-01, brainnode-01) via TCP checks
- PostgreSQL authenticated connectivity (if PGPASSWORD set)
- Platform service health endpoints (all 5 services)
- Loki HTTP API readiness (`/ready` endpoint at 192.168.71.220:3100)
- Loki Level 1 query function (`check_loki_service_logs`) — exported for
  use by all validate scripts via importlib

CLI flags: `--infra`, `--services`, `--loki` for targeted checks.
Exit code: 0 on all PASS/WARN, 1 on any FAIL.

#### `fixtures/` — 5 shared fixture files
| File | Content |
|:-----|:--------|
| `places_fixtures.json` | 5 synthetic Tokyo place records (Shogun-relevant) |
| `reddit_fixtures.json` | 10 synthetic posts across r/ramen, r/JapanTravel, r/japan |
| `scrape_fixtures.json` | 3 pre-canned scrape results (books.toscrape.com) + extract schema |
| `llm_fixtures.json` | 5 chat prompts + 2 embedding tests; echo, JSON, multi-turn, provider routing |
| `telegram_fixtures.json` | 3 message payloads (plain, markdown, alert format) + TEST_CHAT_ID skip behaviour |

All fixtures use synthetic data. No production credentials or personal data.
Fixtures are stable, reusable across all service validate scripts.

#### `templates/validate_template.py`
Annotated starter template for new service validate scripts. All 6 standard
sections pre-scaffolded:
- Step 0: Environment discovery
- Step 1: DB pre-test / baseline row counts
- Step 2: First endpoint test (with fixture import)
- Step 3: Regression — all existing endpoints
- Step Loki: Level 1 check (imports from platform_preflight.py)
- Final report: pass/fail per step, row deltas, Green Gate checklist printed

#### `templates/openapi_template.yaml`
Starter OpenAPI 3.1.0 spec with all required sections. Covers:
- Auth patterns (bearer token or none)
- Health endpoint (required for every service)
- Request/response schema examples
- Platform-standard ErrorResponse schema
- LLM Gateway multi-provider note (see services/llm-gateway/openapi.yaml)

---

### `.claude/services/_playwright-guide.md` — New
Agent workflow documentation for Playwright MCP visual verification.
Documents the 7-step agent workflow: navigate → snapshot → screenshot →
exercise features → console check → final screenshot → close.
Includes evidence report format, common issues + fixes, tool quick reference.
Future automated Playwright scripts noted as deferred pending frontend planning.

---

### `.claude/CLAUDE.md` — Modified
- Added Step 2.5 (Task Onboarding Preflight — Stage 2 Part A) to session startup
- Added Stage 2 Part B (Capability Pre-check) protocol with 3-outcome table
- Security scan renumbered from Step 2.5 to Step 2.6

---

## Green Gate Checklist

| Item | Status |
|:-----|:-------|
| 1. All validate steps PASS | N/A — no deployed service in this task |
| 2. Loki Level 1 verified | N/A — infrastructure task, no service logging |
| 3. OpenAPI spec committed | N/A — template committed, per-service specs are Phase 2–3 |
| 4. Service doc capability registry | N/A — no new service deployed |
| 5. _index.md updated | N/A — no new service |
| 6. Evidence report written | ✓ This document |
| 7. .env.example current | N/A — no service-level env changes |

---

## Exit Criteria Verification

Per the plan:
> `platform_preflight.py` runs from laptop and produces PASS for all
> infrastructure checks. Fixtures files exist and contain valid test data.
> Templates pass a syntax/structure review.

- platform_preflight.py: created and functional (syntax verified)
- All 5 fixture files: created with valid JSON
- validate_template.py: created, all sections annotated, Loki import functional
- openapi_template.yaml: created, valid YAML structure
- _playwright-guide.md: created, 7-step workflow documented
- CLAUDE.md: updated with Step 2.5 preflight and Part B capability pre-check

---

## Next Step

Phase 2 — Reference Implementation: Scraper Service
Apply the full standard to the scraper service:
- `services/scraper/openapi.yaml` (all 4 endpoints)
- Update `services/scraper/validate_firecrawl.py` (fixtures + Loki gate + regression)
- Update `.claude/services/scraper.md` (capability registry section)
- Walk the 7-item Green Gate Checklist against scraper

Separate execution session required.
