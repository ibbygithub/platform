# Plan: MCP Infrastructure — Two-Environment Strategy
Date: 2026-03-09
Status: Approved — phased execution

## Objective

Deploy MCP (Model Context Protocol) servers across two distinct environments:
1. **Environment 1** — Claude Code agent tools on ibbytech-laptop, giving the
   agent browsing, GitHub, database, and memory capabilities during coding sessions.
2. **Environment 2** — Platform-level MCP servers on svcnode-01 that application
   projects (starting with Shogun) use for AI tool calling.

## Scope

**In scope:**
- Environment 1: Four foundational MCP servers on ibbytech-laptop (Playwright,
  GitHub, PostgreSQL, Memory)
- Environment 2: Phase 1 — PostgreSQL MCP and Memory MCP on svcnode-01
- Environment 2: Phase 2 — LLM Gateway tool orchestration (Option C), scoped to
  when OpenRouter is added as a platform service

**Explicitly out of scope:**
- Shogun application architecture and frontend (separate project conversation)
- Google API/Workspace MCP integration (separate conversation — auth setup required first)
- NotebookLM MCP (no official server; deferred until a vendor-backed option exists)
- Garmin fitness integration (separate low-priority project)
- OpenRouter platform service (separate planning session; dependency for Phase 2)

## Current State

- svcnode-01 runs: LLM gateway, scraper, Google Places, Telegram, Reddit gateway
  (all REST APIs on platform_net, behind Traefik)
- dbnode-01: platform_v1 and shogun_v1 with pgvector. `mcp_shogun` role and
  `mcp_group` grants on shogun_v1 already exist (dormant — created for a prior
  MCP attempt that did not complete)
- n8n: being decommissioned — automation workflows will be cron-based Python
  services on brainnode-01 or svcnode-01 going forward
- ibbytech-laptop: Claude Code installed, Node.js available, no MCP servers
  currently configured
- Shogun LLM: Gemini 2.0 Flash (direct API). No MCP integration today.
  Shogun reboot scheduled 2026-03-10.

## Key Architectural Decisions

### MCP Protocol and Gemini Compatibility
Gemini 2.0 Flash uses Google's Function Calling API, not MCP protocol.
MCP is designed for Claude. These are not interchangeable without a translation
layer. Decision: Do NOT build MCP integration into Shogun during the reboot.
Shogun reboot uses direct REST calls to platform services (proven pattern).
MCP integration is added in Phase 1 (post-Shogun MVP) via a gateway adapter.

### Option C — LLM Gateway as Tool Orchestration Layer
When OpenRouter is added as a platform service (future), the LLM gateway is
enhanced to handle tool dispatch. MCP servers register their tool schemas with
the gateway. The gateway translates between the active model's native tool format
(Gemini Function Calling, Claude MCP, OpenRouter models) and MCP protocol.
Application code calls the gateway only — model and tool protocol are abstracted.
This is the target architecture. It is NOT built during the Shogun reboot.
It is scoped to the OpenRouter planning session.

### Domain Separation — REST APIs vs MCP Servers
Platform REST gateways (scraper, places, LLM, Telegram, Reddit) remain as-is.
MCP servers are deployed as separate containers on svcnode-01, separate
docker-compose stacks, separate Traefik routes. They do not colocate with or
replace existing REST gateways. If an MCP server is deprecated or the protocol
changes, the REST layer is unaffected.

### MCP Server Evaluation Framework
Before installing any MCP server (from mcpmarket.com or elsewhere):
1. Is it from the official MCP org, the vendor themselves, or has >2k GitHub
   stars with recent commits? If no — skip.
2. Does it do something not already achievable with existing platform tools? If no — skip.
3. Does its auth model avoid plaintext credential storage? If no — skip.
4. Is it vendor-backed or actively maintained? If not confident — defer.

---

## Environment 1 — Claude Code Agent Tools (ibbytech-laptop)

### Configuration Location
`C:\Users\toddi\.claude\` — global Claude Code config directory.
MCP servers configured here are available in all project sessions.

### Approved MCP Servers — Tier 1 (Install First)

| Server | Package | Maintained By | Purpose |
|--------|---------|---------------|---------|
| Playwright | `@playwright/mcp` | Microsoft / Playwright team | Browse URLs, interact with pages, extract content during sessions |
| GitHub | `github-mcp-server` | GitHub (official) | Read repos, issues, PRs, code search across all projects |
| PostgreSQL | `@modelcontextprotocol/server-postgres` | MCP org (official) | Query platform_v1 and shogun_v1 directly during sessions |
| Memory | `@modelcontextprotocol/server-memory` | MCP org (official) | Persist key facts across Claude Code sessions (project context, decisions) |

### Approved MCP Servers — Tier 2 (After Tier 1 is stable)

| Server | Condition for addition |
|--------|----------------------|
| Grafana MCP | Evaluate when official Grafana Labs server is confirmed stable |

### On Hold

| Server | Reason |
|--------|--------|
| Firecrawl MCP | Platform already has working REST gateway; MCP adds no capability |
| NotebookLM MCP | No official Google server; community builds are unstable |
| Google Workspace MCP | Auth setup required first — separate conversation |
| Any mcpmarket.com server not listed above | Apply evaluation framework before considering |

### Execution Notes
- All Tier 1 servers are Node.js-based; run via `npx` or global npm install
- PostgreSQL MCP requires connection string to dbnode-01 — use `dba-agent`
  credentials scoped read-only for agent sessions; do not use `postgres` superuser
- Memory MCP stores to local file by default; acceptable for laptop-resident use
- GitHub MCP requires a GitHub personal access token scoped to repos only

---

## Environment 2 — Platform MCP Servers (svcnode-01)

### Architectural Principle
MCP servers are a separate platform service tier, not replacements for REST gateways.
They run as Docker containers on platform_net, with Traefik routing under
`*.platform.ibbytech.com` (internal only — no public exposure).

### Phase 1 — Post-Shogun MVP (target: ~2 weeks after reboot)

#### 1. PostgreSQL MCP Server
Exposes shogun_v1 (and optionally platform_v1) as AI-queryable tools.
The dormant `mcp_shogun` role and `mcp_group` grants on shogun_v1 are already
in place — this was prepared for exactly this purpose.

- Container: `platform-postgres-mcp`
- Network: platform_net
- Traefik route: `postgres-mcp.platform.ibbytech.com` (internal)
- Auth: `mcp_shogun` role (read: SELECT on shogun_v1 public schema)
- Server: Official PostgreSQL MCP server or pgmcp (evaluate at execution time)
- Scope: shogun_v1 initially; platform_v1 added when needed by other projects

#### 2. Memory MCP Server — User Profile Memory
Provides persistent, user-scoped memory for Shogun AI interactions.
Backed by pgvector in platform_v1 or shogun_v1 for semantic retrieval.

This is not a simple key-value store. The Shogun memory model requires:
- Per-user profiles (preferences, dietary needs, shopping goals, personality)
- Entity tracking (stores, locations, events with status and attributes)
- Todo/action lists with geofence trigger metadata
- Updateable via natural language ("the knife store in Osaka was closed")

Technology choice (to be vetted at Phase 1 execution):
- Candidate A: `@modelcontextprotocol/server-memory` + custom pgvector extension
- Candidate B: Mem0 (purpose-built user memory for AI agents, pgvector backend)
- Candidate C: Custom FastAPI memory service exposing MCP tool interface

Decision deferred to Phase 1 planning — requires a separate vetting session.
Mem0 is the leading candidate given its design intent matches the requirement exactly.

- Container: `platform-memory-mcp`
- Network: platform_net
- Traefik route: `memory-mcp.platform.ibbytech.com` (internal)
- Scope: platform-wide (Shogun first; other projects connect as needed)

### Phase 2 — Option C Gateway Enhancement (scoped to OpenRouter planning session)

When OpenRouter is added as a platform service:
- LLM gateway is enhanced to accept tool schemas from registered MCP servers
- Gateway handles protocol translation: OpenRouter/Gemini Function Calling ↔ MCP
- Application code (Shogun and others) calls gateway only — model and tool
  protocol are fully abstracted
- MCP servers from Phase 1 register their schemas with the gateway at startup

This phase is NOT designed here. It is a deliverable of the OpenRouter planning
session, which must precede it.

### What Shogun Uses During Reboot (Pre-Phase 1)

| Capability | Mechanism | Notes |
|-----------|-----------|-------|
| Database queries | Direct PostgreSQL via psycopg2 | Proven pattern from platform services |
| Google Places | REST call to places.platform.ibbytech.com | Already deployed |
| Web scraping | REST call to scraper.platform.ibbytech.com | Already deployed |
| LLM completions | REST call to LLM gateway | Already deployed |
| Telegram interface | Telegram Bot API direct | Already in use |
| Location awareness | Telegram location sharing (tested) | In Shogun test harness |

None of this changes in Phase 1. MCP adds a tool-calling layer on top.
The REST gateways remain and continue to serve non-AI consumers.

---

## Dependencies

| Dependency | Blocks | Status |
|-----------|--------|--------|
| Node.js on ibbytech-laptop | Environment 1 execution | Available |
| GitHub personal access token | GitHub MCP (Env 1) | Must be created |
| dbnode-01 read-only MCP credentials | PostgreSQL MCP (Env 1 + Env 2) | Must be provisioned (dba-agent task) |
| Shogun MVP stable | Phase 1 (Env 2) | Shogun reboot 2026-03-10 |
| OpenRouter planning session | Phase 2 (Env 2) | Not started |
| Google API auth setup | Google MCP servers (both envs) | Separate conversation |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| MCP server deprecated after install | Medium | Low | Domain separation (REST gateways unaffected) |
| Gemini Function Calling ↔ MCP bridge complexity underestimated | Medium | High | Deferred to OpenRouter session; don't build early |
| Memory data model too simple for Shogun entity tracking | High | Medium | Vet Mem0 carefully at Phase 1 — don't default to key-value |
| Community MCP servers introducing security exposure | Medium | High | Apply evaluation framework; no untested servers |
| pgvector-backed memory requires schema design before Phase 1 | Low | Medium | Include memory schema in Shogun reboot DB planning |

---

## Execution Sequence

```
Week of 2026-03-09:
  [1] Environment 1 — Install Tier 1 MCP servers on ibbytech-laptop
      Execution agent: devops-agent persona not required (laptop-local)
      Branch: feature/20260309-env1-mcp-setup
      Deliverable: Claude Code sessions have Playwright, GitHub, PostgreSQL, Memory

  [2] Shogun reboot (separate project conversation)
      Direct REST API pattern — no MCP integration yet

2 weeks post-reboot (Shogun MVP stable):
  [3] Environment 2 Phase 1 — PostgreSQL MCP + Memory MCP on svcnode-01
      Requires: separate planning session for Memory technology vetting
      Branch: feature/YYYYMMDD-env2-mcp-phase1

Future (OpenRouter planning session):
  [4] Environment 2 Phase 2 — Option C gateway enhancement
```

---

## Open Items

- Memory MCP technology choice (Mem0 vs. custom) — vetting session required
  before Phase 1 execution
- Google API auth scope audit — required before any Google MCP server work
- OpenRouter platform service planning — gates Phase 2
- GitHub personal access token scope — define minimum required scope before
  GitHub MCP installation
- Read-only MCP database credentials for Env 1 PostgreSQL MCP — dba-agent task
