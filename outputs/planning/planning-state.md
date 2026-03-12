# Planning State — IbbyTech Platform
Last updated: 2026-03-11 (Phase 4 complete)

## Project Summary
IbbyTech home lab enterprise-lite platform. Primary proving ground application
is Project Shogun — an AI travel concierge service for Japan trips (family use,
~3 users). Platform services (scraper, Google Places, LLM gateway, Telegram,
Reddit) are deployed on svcnode-01 and built here first for reuse in future
projects. n8n is being decommissioned — automation workflows will be custom
cron-based Python services. mltrader (ML trading bot) is a planned future project.

## Active Work
| Item | Description | Phase | Status | Last Updated |
|------|-------------|-------|--------|--------------|
| Scraper service | Web scraper backed by Firecrawl on svcnode-01 | Production | Complete | 2026-03-05 |
| Google Places gateway | Places search and storage | Production | Complete | 2026-03-06 |
| LLM gateway | LLM completion service on svcnode-01 | Production | Complete | 2026-03-01 |
| Reddit gateway | Credential-free v2, deployed, tested | Production | Complete | 2026-03-08 |
| MVP Testing Dashboard | localhost:8000 platform test harness | Production | Complete | 2026-03-08 |
| MCP Infrastructure — Env 1 | Playwright, GitHub, PostgreSQL, Memory MCP on laptop | Complete | All 4 Tier 1 servers connected 2026-03-11 | 2026-03-11 |
| MCP Infrastructure — Env 2 | Platform MCP servers on svcnode-01 | Phase 1 deferred | Awaiting Shogun MVP stability | 2026-03-09 |
| Platform Test Standard | Dev cycle, test harnesses, green gate for all services | All 4 phases complete | Complete 2026-03-11 | 2026-03-11 |

## Open Decisions
- **Google Places routing:** `platform_v1.places` vs `shogun_v1.places` — canonical
  dataset ownership unresolved. Must be decided before Shogun build begins.
- **Memory MCP technology choice:** Mem0 vs. @modelcontextprotocol/server-memory +
  custom vs. bespoke FastAPI service. Requires vetting session before Env 2 Phase 1.
- **Option C (LLM gateway tool orchestration):** Design deferred to OpenRouter
  planning session. Do not build before OpenRouter architecture is decided.
- **Google API auth scope:** Which Google APIs are currently enabled on the
  existing key? Separate conversation required before any Google MCP work.

## Technology Registry
| Technology | Role | Rationale | Date |
|------------|------|-----------|------|
| Traefik v3 | Reverse proxy on svcnode-01 | Label-based Docker service discovery, automatic cert management | 2026-03-01 |
| PostgreSQL 17 | Primary database on dbnode-01 | Enterprise-grade, pgvector support | 2026-02-15 |
| Docker Compose | Service orchestration | Standard for multi-service deployment on svcnode-01 | 2026-02-15 |
| Firecrawl | Web scraping engine | Managed service with JS rendering | 2026-03-04 |
| Python 3.x | Service runtime | Default for platform services | 2026-02-15 |
| FastAPI | Web framework | Python-first, async — used for platform services and Shogun | 2026-03-07 |
| pdfplumber | PDF text extraction | Cleanest API, pure Python | 2026-03-07 |
| python-docx | Word document extraction | De facto standard for .docx | 2026-03-07 |
| SQLite | Local embedding store (MVP dashboard only) | Throwaway MVP — upgrade path to pgvector documented | 2026-03-07 |
| OpenAI embeddings | text-embedding-3-small | Consistent with scraper, key in platform .env | 2026-03-07 |
| Gemini 2.0 Flash | Shogun LLM (current) | Strong results, low cost, multimodal (receipt OCR) | 2026-03-09 |
| MCP @playwright/mcp | Claude Code agent browser tool | Microsoft-maintained, web browsing during sessions | 2026-03-09 |
| MCP github-mcp-server | Claude Code agent GitHub tool | GitHub official, repo/issue/PR access | 2026-03-09 |
| MCP server-postgres | Claude Code agent DB tool | MCP org official, direct DB query during sessions | 2026-03-09 |
| MCP server-memory | Claude Code agent memory | MCP org official, persist context across sessions | 2026-03-09 |

## Decision Log

### Reverse Proxy Selection — 2026-03-01
- Capability need: Route HTTP traffic to multiple services on svcnode-01
- Options considered: nginx, Caddy, Traefik v3, HAProxy
- Decision: Traefik v3
- Reasoning: Label-based Docker service discovery, native Let's Encrypt
- Risk accepted: None significant

### Scraper Firecrawl Connection Pattern — 2026-03-06
- Capability need: Scraper service must reach Firecrawl across separate Docker networks
- Options considered: Join firecrawl to platform_net, host.docker.internal, direct IP
- Decision: host.docker.internal:3002 (HOST_IP pattern)
- Reasoning: Firecrawl root-owned legacy service on separate network
- Risk accepted: Host network dependency — if Firecrawl port changes, scraper .env must update

### MVP Dashboard Technology — 2026-03-07
- Decisions: pdfplumber + python-docx, local SQLite for MVP, FastAPI + Jinja2
- Reasoning: Speed to build, fully throwaway for MVP scope
- Risk accepted: SQLite embeddings need re-generation on migrate to pgvector

### MCP Protocol Strategy — 2026-03-09
- Capability need: AI tool calling for Shogun and Claude Code agent sessions
- Problem identified: Gemini 2.0 Flash uses Function Calling API, not MCP protocol.
  Building MCP servers for Shogun during the reboot would require a translation
  layer that competes with the frontend delivery timeline.
- Options considered:
  - Option A: Switch Shogun to Claude (native MCP)
  - Option B: Keep Gemini, build Function Calling ↔ MCP adapter
  - Option C: LLM gateway as model-agnostic tool orchestration layer
- Decision: Option C — deferred to OpenRouter planning session
- Reasoning: Shogun reboot uses direct REST calls (proven, no risk). Option C is
  designed once, correctly, when OpenRouter is added as a platform service.
  Option B creates maintenance burden for every MCP schema change.
- Risk accepted: No MCP tool calling in Shogun until after MVP is stable (~2 weeks)

### MCP Domain Separation — 2026-03-09
- Decision: REST API gateways and MCP servers are separate containers, separate
  docker-compose stacks, separate Traefik routes. No colocation.
- Reasoning: MCP protocol lifecycle is independent of REST API stability.
  If MCP servers are deprecated or change, REST gateways are unaffected.
- Risk accepted: None — this reduces risk

### n8n Decommission — Automation Replacement Pattern — 2026-03-09
- Decision: n8n is being decommissioned. Automation workflows become custom
  cron-based Python services on brainnode-01 or small svcnode-01 services.
- Reasoning: User preference to build automations with Claude Code agent directly.
  Keeps platform stack coherent and eliminates n8n maintenance burden.
- Impact: YouTube monitoring, RSS, calendar sync, and similar automations will
  be purpose-built Python services, not n8n workflows.
- Risk accepted: More custom code to maintain, but full control over behavior

## Development Cycle Standard (Active — 2026-03-11)

The platform has a formally defined 5-stage development cycle. Every build task
must follow it. Defined in: `outputs/planning/platform-test-standard-plan.md`

**5 Stages:**
1. Session Startup (platform health, git state, security scan)
2. Task Onboarding — Part A: infrastructure readiness; Part B: Capability Pre-check
3. Build (API-first: OpenAPI spec before code)
4. Post-Deployment Validation (smoke + regression + Loki Level 1)
5. Delivery Gate (7-item Green Checklist — all must pass)

**Green Checklist (required for every service task):**
- [ ] 1. All validate script steps PASS (including regression)
- [ ] 2. Loki Level 1 verified (service= label logs in Loki, last 15 min)
- [ ] 3. OpenAPI spec committed to services/{name}/openapi.yaml
- [ ] 4. Service doc capability registry current
- [ ] 5. _index.md updated
- [ ] 6. Evidence report in outputs/validation/
- [ ] 7. .env.example current

**Future gates (tracked, not yet active):**
- Loki Level 2: Grafana panel per service (triggers after Phase 3 complete)
- Synthetic monitoring via brainnode-01 cron (triggers after brainnode-01 onboarded)
- Automated Playwright tests for frontends (triggers after frontend planning session)

## Backlog
- **Shogun reboot:** Separate project conversation. FastAPI, Docker, svcnode-01.
  Frontend (mobile-friendly dashboard): weather, blossom tracking, local news,
  calendar, lodging/contacts/itinerary. Reboot date: 2026-03-10.
  Tech: Gemini 2.0 Flash, Telegram bot interface, direct REST calls to platform.
- **OpenRouter platform service:** Model selection per application. Required before
  Option C (LLM gateway tool orchestration) can be designed. Own planning session.
- **MCP Env 2 — Memory technology vetting:** Mem0 vs. alternatives. Required
  before Phase 1 execution (~2 weeks post Shogun MVP).
- **Google API auth audit:** Which APIs are currently enabled on existing key?
  Required before Google Maps/Calendar/YouTube/Translate MCP work begins.
- **Google Workspace CLI evaluation:** googleworkspace/cli is a CLI tool, not
  an MCP server. If Workspace integration (Calendar, Drive, Gmail) is needed,
  requires separate vetting. Separate conversation.
- **Translation services (Japanese ↔ English, written + spoken):** Google Translate
  and Speech-to-Text APIs. Deferred until Google API auth is resolved.
- **YouTube monitoring service:** Cron-based Python, saves to DB/folder.
  Deferred post-Shogun MVP.
- **RSS feed service:** Cron-based Python. Deferred post-Shogun MVP.
- **Expense tracking:** Web page in Shogun app. Image OCR via Gemini multimodal
  (receipt photo → structured data). Deferred to Shogun Phase 2.
- **Location-aware geofencing:** Alert when near saved location (knife store
  Tokyo example). Requires memory entity model with geofence metadata. Design
  during Memory MCP vetting session.
- **Garmin fitness integration:** Low priority, own project. Not in active backlog.
- **Twitter/X gateway:** Planned 2026-03-10. Full plan written and saved.
  Uses twscrape library against Twitter's internal mobile GraphQL API.
  Requires 2–3 dedicated Twitter accounts (free tier, non-personal identity)
  before Phase 0 can start. Account pool stored in .env. Stricter rate limits
  than Reddit gateway (20 req/min vs 50). Two open items before execution:
  (1) account identity process, (2) Shogun seed feed search terms.
  See: outputs/planning/twitter-gateway-plan.md
- **mltrader project:** Not started, planning not yet initiated.
- **brainnode-01 onboarding:** No projects deployed yet. SSH key and git
  permissions needed before any service can be deployed there.

## Planning Documents
| Document | Path | Status |
|----------|------|--------|
| MVP Testing Dashboard Plan | outputs/planning/mvp-dashboard-plan.md | Complete |
| MCP Infrastructure Plan | outputs/planning/mcp-infrastructure-plan.md | Approved — phased execution |
| Twitter/X Gateway Plan | outputs/planning/twitter-gateway-plan.md | Backlogged — not started |
| Platform Test Standard Plan | outputs/planning/platform-test-standard-plan.md | Complete — all 4 phases delivered 2026-03-11 |
