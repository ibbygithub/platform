# Plan: IbbyTech Platform — Development Cycle & Test Standard
Date: 2026-03-11
Status: Approved — pending Phase 1 execution

---

## Objective

Define and implement a reusable test standard and development cycle for the
IbbyTech Platform. Every service built on this platform — current and future —
must pass the same "green gate" before it is considered complete. The 5
existing services (scraper, LLM gateway, Google Places, Reddit gateway,
Telegram gateway) are used as the retroactive reference implementations.
The scraper service is the Phase 1 reference: the full standard is proved
there first, then applied to the remaining 4 and templated for all future builds.

---

## Scope

**Included:**
- Full development cycle standard: session startup → onboarding → build → post-deploy → delivery gate
- Capability Pre-check framework (see below)
- Shared test fixture library (`tools/test-harness/fixtures/`)
- Platform Preflight script (`tools/test-harness/platform_preflight.py`)
- Validate script standard and template (extending validate_firecrawl.py pattern)
- Loki Level 1 observability gate (automated, required for green)
- OpenAPI spec standard (one spec per service, required for green)
- OpenAPI spec for LLM gateway covering all three providers (OpenAI, Gemini, Anthropic)
- Delivery Checklist (7-item green gate applied at task completion)
- Playwright agent workflow documentation (for Claude Code agent visual verification)
- Playwright automated test script standard (details deferred pending frontend planning)
- Retroactive application to all 5 existing services

**Explicitly excluded:**
- Unit tests (not applicable — services are integration-heavy by design)
- Loki Level 2 Grafana dashboard gate (tracked as future action, see below)
- Automated Playwright test scripts for frontend (deferred — frontend architecture
  not yet decided. Own planning session required. See: Future Actions)
- Synthetic monitoring via brainnode-01 cron (tracked as future action)
- Load testing (not applicable at this scale — 3 users)

---

## Core Concepts

### The Development Cycle — Five Stages

Every build task on this platform follows five stages in sequence.
No stage may be skipped without documented justification.

```
STAGE 1 — SESSION STARTUP
  Platform health check (all services reachable)
  Git state check (per CLAUDE.md protocol)
  Security scan (per CISO skill)
  Output: Session Brief with infrastructure status

STAGE 2 — TASK ONBOARDING (pre-build, before first line of code)
  Part A — Infrastructure Readiness
    All nodes reachable (svcnode-01, dbnode-01, brainnode-01 if needed)
    All dependent platform services healthy (health endpoint check)
    DB connectivity confirmed for required schema
    Required credentials present in .env
  Part B — Capability Pre-check
    For each feature the task requires from an upstream service:
      1. Is the feature available from the upstream API/service?
      2. Is the feature documented in our platform service doc?
    Outcomes:
      AVAILABLE + DOCUMENTED   → proceed, feature is ready to consume
      AVAILABLE + UNDOCUMENTED → flag gap, document before or during build
      NOT AVAILABLE            → hard stop, report before any work starts

STAGE 3 — BUILD
  API-first: OpenAPI spec drafted/updated before coding starts
  Feature branch created (feature/YYYYMMDD-task-slug)
  Code written, committed incrementally
  .env.example updated for any new variables
  Every commit leaves service in a runnable state

STAGE 4 — POST-DEPLOYMENT VALIDATION
  New feature smoke test: does the new capability work end-to-end?
  Regression test: do all existing endpoints still return expected responses?
  DB write verification: before/after row counts confirm persistence
  Loki Level 1 check: structured logs with service= label flowing to Loki
  Final report written to outputs/validation/

STAGE 5 — DELIVERY GATE (Green Checklist)
  All seven items must pass. No exceptions without human approval.
  See Delivery Checklist below.
```

---

### Capability Pre-check Framework

The Capability Pre-check runs at the start of every task that consumes an
upstream platform service or external API. It answers two questions before
any build work starts:

**Question 1: Can the upstream do this?**
Each platform service maintains a capability registry in its service doc
under a `## Capabilities` section. Each capability entry records:
- Capability name
- Endpoint or method that provides it
- Documented status: `implemented` | `available-upstream` | `not-available`
- Last verified date

Example entry (Google Places service doc):
```
| place_photos      | GET /v1/places/{id}/photos  | available-upstream | 2026-03-11 |
```
Status `available-upstream` means: the Google Places API supports this, but
our platform gateway does not yet expose it. A task that needs place photos
will see this status and know: the feature exists upstream, but implementation
work is required in this task.

**Question 2: Is it documented in our platform layer?**
If status is `implemented`, the platform gateway exposes it and it is safe to
consume. If `available-upstream`, the feature exists but requires platform
implementation — the task scope expands to include it. If `not-available`,
stop and report before the task begins.

**Implementation:** The capability registry is a section in each service doc
(`.claude/services/{name}.md`). The onboarding check reads the relevant
service doc and presents the capability matrix for features the task needs.
This is a documentation discipline enforced at Stage 2, not a script that
queries the API (though Stage 4 validate scripts verify actual behavior).

---

### Validate Script Standard

Every platform service must have a `validate_{service}.py` script.
Location: `services/{service-name}/validate_{service}.py`

Required sections (following the validate_firecrawl.py pattern):

```
Step 0 — Environment Discovery
  Print all required env vars (mask secrets)
  Verify all upstream dependencies are reachable
  Hard stop if any required credential or dependency is missing

Step 1 — Pre-Test DB State
  Connect to required database and schema
  Capture baseline row counts for all service tables
  Hard stop if DB connection fails

Step 2..N — Functional Tests (one step per service endpoint)
  Test every declared endpoint with a controlled test payload
  Use fixtures from tools/test-harness/fixtures/ where applicable
  Verify response structure matches OpenAPI spec
  Persist test results to DB where applicable
  Verify persistence (read-back confirmation)

Step N+1 — Loki Level 1 Check
  Query Loki HTTP API for recent log entries from this service
  Filter: service={service-name} label, last 15 minutes
  Pass: at least one structured log entry found
  Fail: no entries found, or Loki unreachable

Step N+2 — Final Validation Report
  Pass/fail per step
  Row count deltas (before/after)
  Total elapsed time
  Overall result: PASS (all steps) or FAIL (list failing steps)
```

Test payloads must use controlled, safe data from the shared fixtures library.
Tests must not depend on live production data being present.
Tests must be idempotent — safe to run multiple times.

---

### Shared Fixture Library

Location: `tools/test-harness/fixtures/`

Purpose: controlled, stable test data usable across all service validate scripts.
Prevents test data rebuild from scratch on every service build.

Fixtures defined at plan approval:

| File | Content | Used by |
|:-----|:--------|:--------|
| `places_fixtures.json` | 5 synthetic place records (Tokyo locations, Shogun-relevant) | Places gateway, Shogun tests |
| `reddit_fixtures.json` | 10 post/comment records (r/japan, r/ramen content) | Reddit gateway |
| `scrape_fixtures.json` | 3 pre-canned scrape results (books.toscrape.com pages) | Scraper service |
| `llm_fixtures.json` | 5 standard prompt/response pairs (known format, not content) | LLM gateway |
| `telegram_fixtures.json` | 3 test message payloads (non-production chat ID required) | Telegram gateway |

Additional fixture files added as new services are built (Twitter, Shogun, etc.)

---

### Delivery Checklist — The Green Gate

Seven items. All must be checked before a service task is marked complete.
No partial credit. No "we'll do it later."

```
[ ] 1. All validate script steps PASS
        (includes regression tests for existing endpoints)
[ ] 2. Loki Level 1 verified
        (structured logs with service= label, last 15 minutes, confirmed in Loki)
[ ] 3. OpenAPI spec committed to services/{name}/openapi.yaml
        (covers all endpoints, request/response schemas, error codes)
[ ] 4. Service doc updated in .claude/services/{name}.md
        (capability registry current, all new endpoints documented)
[ ] 5. _index.md updated with any new or changed service entry
[ ] 6. Evidence report written to outputs/validation/
        (validate script output captured, checklist status included)
[ ] 7. .env.example current
        (all required env vars present with descriptions, no secrets)
```

Items 1–2 are automated (script output determines pass/fail).
Items 3–7 are documentation and evidence artifacts (human + agent verify).

---

### OpenAPI Spec Standard

Every service requires an OpenAPI 3.x spec at `services/{name}/openapi.yaml`.

Minimum required content:
- `info`: service name, version, description
- `servers`: internal platform URL (e.g., `http://scrape.platform.ibbytech.com`)
- `paths`: every endpoint with request body schema and response schemas
- `components/schemas`: all request and response types defined
- `components/securitySchemes`: auth method documented (bearer token or none)

**LLM Gateway spec (special case — Option A):**
The LLM gateway spec must cover all three provider paths:
- OpenAI-backed endpoints (`provider: openai`)
- Google Gemini-backed endpoints (`provider: google`)
- Anthropic-backed endpoints (`provider: anthropic`)

Each provider variant documented with its model identifiers, supported
parameters, and response shape differences. The spec is the reference for
any service (Shogun, MCP servers, automation scripts) that calls the LLM gateway.

---

### Playwright Agent Workflow (Claude Code sessions)

Documented pattern for Claude Code agent visual verification of deployed
web interfaces. Used when a task deploys or modifies a web frontend.

The agent workflow (not an automated script — this is session-time verification):

```
Step 1: Agent uses mcp__playwright__browser_navigate to open the deployed URL
Step 2: Agent uses mcp__playwright__browser_snapshot to capture the page state
Step 3: Agent visually inspects the snapshot for expected UI elements
Step 4: Agent uses mcp__playwright__browser_click or browser_fill_form
        to exercise interactive features
Step 5: Agent captures evidence screenshot via mcp__playwright__browser_take_screenshot
Step 6: Screenshot path referenced in evidence report
```

This workflow is triggered whenever a task deliverable includes a web UI.
It replaces "manually open a browser and check" with a documented,
reproducible agent-driven verification step.

Automated Playwright test scripts (independent of agent sessions) are a
separate deliverable — deferred pending frontend architecture planning.
See Future Actions below.

---

## Phases

---

## Architecture Decisions

### Loki Level 1 Query Pattern — 2026-03-11
- **Decision:** Validate scripts query Loki HTTP API directly from the laptop
- **Endpoint:** `http://192.168.71.220:3100` (svcnode-01, Loki default port)
- **Query:** LogQL — `{service="<name>"}` with `start` set to 15 minutes ago
- **Pass condition:** At least one log entry returned
- **Fail condition:** No entries, or HTTP error from Loki
- **Confirmed:** Loki port 3100 reachable from laptop on internal network — 2026-03-11

---

### Phase 1 — Platform Test Infrastructure Foundation
**Goal:** The shared infrastructure exists. Templates are ready. The delivery
checklist is formally defined. The platform preflight script runs at task start.

Entry criteria: This plan approved
Deliverables:
  - `tools/test-harness/` directory structure created
  - `tools/test-harness/platform_preflight.py` — master infrastructure readiness
    check (extends validate_connectivity.py, adds DB schema checks, credential checks,
    Loki reachability, structured output with PASS/FAIL per check)
  - `tools/test-harness/fixtures/` — all 5 initial fixture files populated
  - `tools/test-harness/templates/validate_template.py` — annotated starter template
    for new service validate scripts (all 6 standard sections, fixtures import)
  - `tools/test-harness/templates/openapi_template.yaml` — starter OpenAPI spec
    with required sections pre-filled
  - Delivery Checklist defined (this document — checklist section above)
  - Playwright agent workflow documented in `.claude/services/_playwright-guide.md`
  - CLAUDE.md updated: Stage 2 onboarding check added to task protocol
Exit criteria:
  `platform_preflight.py` runs from laptop and produces PASS for all
  infrastructure checks. Fixtures files exist and contain valid test data.
  Templates pass a syntax/structure review.
Complexity: Medium
Node: laptop only (no SSH required for Phase 1)

---

### Phase 2 — Reference Implementation: Scraper Service
**Goal:** The full standard applied to scraper, end-to-end. This proves the
standard works against a real service and produces the reference that all
other services follow.

Entry criteria: Phase 1 complete
Deliverables:
  - `services/scraper/openapi.yaml` — full spec for all 4 endpoints
  - `services/scraper/validate_firecrawl.py` updated:
    - Uses shared fixtures (books.toscrape.com → scrape_fixtures.json)
    - Adds Loki Level 1 check (new final step)
    - Adds regression check for all 4 endpoints (not just happy path)
  - `.claude/services/scraper.md` updated:
    - Capability registry section added
    - All 4 Firecrawl capabilities documented (scrape, map, crawl, extract)
    - `available-upstream` features flagged (Firecrawl has markdown-only,
      screenshot, and PDF extraction — document if not yet exposed)
  - Delivery Checklist walkthrough: all 7 items verified and documented
  - Evidence report: `outputs/validation/2026-03-11_scraper-test-standard_report.md`
Exit criteria: All 7 delivery checklist items checked. validate script PASS
  including Loki Level 1. OpenAPI spec committed.
Complexity: Medium
Node: laptop (code), svcnode-01 (validate against deployed service)
Persona: devops-agent for SSH checks in validate script

---

### Phase 3 — Apply Standard to Remaining 4 Services
**Goal:** All 5 existing platform services meet the green standard.

Entry criteria: Phase 2 complete (reference implementation proven)
Order of application (easiest → most complex):
  1. Reddit gateway (similar structure to scraper, already well-validated)
  2. Telegram gateway (simpler API surface, fewer endpoints)
  3. Google Places gateway (capability registry needed — place_photos gap to document)
  4. LLM gateway (most complex — Option A spec covering 3 providers)

For each service, deliverables are identical to Phase 2:
  - openapi.yaml committed
  - validate_{service}.py updated (fixtures, Loki gate)
  - service doc capability registry added
  - Delivery Checklist verified
  - Evidence report written

One execution session per service (4 sessions total).
Each session produces its own evidence report.

Complexity: Medium per service, Low for Reddit/Telegram, High for LLM gateway
Node: laptop (code), svcnode-01 (validate)

---

### Phase 4 — Standard Baked Into Build Protocol
**Goal:** The delivery checklist and development cycle stages are referenced
in CLAUDE.md so every future build task inherits them automatically.

Entry criteria: Phase 3 complete (standard validated against all 5 services)
Deliverables:
  - CLAUDE.md updated: Stage 2 Capability Pre-check protocol added to task onboarding
  - CLAUDE.md updated: Delivery Checklist reference added to task completion protocol
  - `.claude/rules/03-platform-standards.md` updated: validate script + OpenAPI
    spec requirements added to Service Documentation section
  - Template service doc updated to include Capability Registry section
Exit criteria: A new service built after Phase 4 inherits the full standard
  without needing to reference this plan document.
Complexity: Low
Node: laptop only

---

## Dependencies

- svcnode-01 must be running (Loki must be reachable from laptop for Level 1 gate)
- Loki HTTP API reachable from laptop on internal network — confirmed 2026-03-11.
  Loki port 3100 is directly accessible. Validate scripts query Loki via HTTP
  from the laptop. No SSH hop required.
- All 5 services must be deployed and reachable for Phase 3 validate runs
- LLM gateway OpenAPI spec (Phase 3) requires human review of all 3 provider
  response shapes — Anthropic and Gemini shapes may differ from OpenAI

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|:-----|:-----------|:-------|:-----------|
| Loki not accessible from laptop on a known port | Medium | Medium | Add SSH-based Loki query to validate template as fallback |
| Scraper validate script update breaks existing test runs | Low | Low | Fixtures are additive — books.toscrape.com still works as fallback |
| LLM gateway OpenAPI spec disagreement on Anthropic response shape | Medium | Low | Human review step before committing spec |
| Capability registry requires auditing all 5 service docs for gaps | Medium | Medium | Phase 2 scraper audit surfaces the pattern; other services follow |

---

## Future Actions (Tracked — Not In Scope)

These are logged here so they are not forgotten. Each requires its own
planning session or execution task before it becomes active.

| Item | Description | Trigger |
|:-----|:------------|:--------|
| Loki Level 2 — Grafana dashboard gate | Each service must have a Grafana panel (request count or error rate) before delivery is complete. Human creates panel; screenshot captured in evidence report. | After Phase 3 completes |
| Synthetic monitoring | validate scripts run on a cron from brainnode-01, alerting via Telegram gateway on failure | After brainnode-01 is onboarded |
| Automated Playwright test scripts | Independent (non-agent) Playwright test suite for web frontends. Details deferred pending frontend architecture planning session. | After Shogun frontend planning session |
| Frontend architecture planning | Shogun frontend tech stack decision. Required before Playwright test scripts can be designed. | User-initiated planning session |
| OpenRouter platform service | Required before Option C (LLM gateway tool orchestration). Own planning session. | When Shogun MVP is stable |

---

## Open Items

1. **Capability registry audit for existing services:** When Phase 2 begins,
   the scraper service doc needs a capability audit — what does Firecrawl
   offer that we haven't yet exposed? Markdown, HTML, screenshot, PDF extraction
   are known capabilities. Confirm which are implemented vs. available-upstream.

---

## Out of Scope

- Unit tests for service business logic (not applicable — integration-heavy services)
- Load testing or performance benchmarking
- DAST/SAST security scanning (covered by CISO skill roadmap, separate track)
- CI/CD pipeline automation (manual deployment + validate pattern is sufficient)
- Production-level staging environment
- Consumer-driven contract testing (Pact or equivalent) — one-team shop
