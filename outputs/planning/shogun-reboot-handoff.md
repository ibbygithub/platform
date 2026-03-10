# Shogun Reboot — Session Handoff
Date: 2026-03-09
Status: Ready to execute — start new session in the Shogun project folder

## What This Is

Project Shogun is an AI travel concierge service, primarily for Japan trip planning.
This document is a handoff from the platform planning session (2026-03-09) to the
Shogun reboot execution session. The previous version of Shogun exists in a separate
project folder and GitHub repo — read that codebase before designing anything new.

## Immediate Priorities (Next 2 Days)

1. **Frontend dashboard** — this is the critical deliverable. Mobile-friendly web page.
2. **Telegram bot** — primary user interface to the Shogun AI agent, already in use.

The frontend and Telegram bot must come up before any MCP or automation work.

---

## Confirmed Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Framework | FastAPI | Matches platform services pattern |
| Deployment | Docker on svcnode-01, platform_net | Standard platform pattern |
| Reverse proxy | Traefik (existing) | Standard — add labels |
| LLM | Gemini 2.0 Flash (direct API) | Strong results, low cost, multimodal |
| Primary UI | Telegram bot | Already in use and tested |
| Secondary UI | Web dashboard (FastAPI route) | Needed in 2 days |
| MCP integration | NOT in this reboot | Deferred — see below |
| Automation engine | Custom Python (n8n decommissioned) | n8n being shut down |

## Platform Services Available (Direct REST — Use These)

All of these are deployed on svcnode-01 and reachable via platform_net:

| Service | URL | Purpose |
|---------|-----|---------|
| LLM gateway | llm.platform.ibbytech.com | LLM completions |
| Google Places | places.platform.ibbytech.com | Place search and storage |
| Scraper | scraper.platform.ibbytech.com | Web scraping via Firecrawl |
| Telegram gateway | telegram.platform.ibbytech.com | Bot messaging |
| Reddit gateway | reddit.platform.ibbytech.com | Reddit search and feeds |

Shogun calls these via HTTP — no MCP, no direct external API calls.
Exception: Gemini 2.0 Flash is called directly (no LLM gateway for Shogun in this phase).

## Users

- Family only — private deployment
- Current: 1 user (owner)
- This week: target 3 users (family members via Telegram)
- Maximum ever: ~6 users
- Per-user memory profiles required (see Memory section below)

## Frontend Dashboard Requirements

Mobile-friendly. Single-page or tab-based layout. Must include:

- **Weather** — current conditions for relevant Japan locations
- **Blossom tracking** — cherry blossom forecast (seasonal relevance)
- **Local news/events** — relevant events at trip destination
- **Calendar** — two modes:
  - Dynamic: editable, add events and places
  - Static: display-only view of confirmed itinerary
- **Trip information panel:**
  - Lodging details (hotel name, address, check-in/out, confirmation numbers)
  - Important contacts (hotels, restaurants, special events)
  - Pre-purchased tickets and reservations
- **Expense tracker page** — separate web page within the app (not Telegram)

## Telegram Bot Requirements

- Primary interface for all AI interaction
- Location sharing already tested in Shogun test harness — wire this up
- Shogun LLM should know the user's current location from Telegram location share
  to provide geolocation context for all queries
- Multimodal: Gemini 2.0 Flash handles image inputs (receipt photos for expenses)

## Expense Tracking

- Entry point 1: Telegram — type "lunch 3000 yen" or snap a receipt photo
- Entry point 2: Web page within the Shogun app
- Gemini 2.0 Flash multimodal reads receipt images and extracts structured data
- Fields: amount, currency, category, who it's for (whole family / specific person),
  location, date
- Storage: database (shogun_v1 — new expense schema needed)

## Memory (Deferred — Do Not Build in Reboot)

Per-user persistent memory is required but NOT part of the reboot scope.
Design it as a stub or placeholder — do not build it yet.

Memory architecture decision is deferred to a separate platform planning session
(Mem0 vs. custom pgvector service). The knife-store example captures the requirement:
- User-profile memory: food preferences, shopping goals, energy preference (peaceful vs. lively)
- Entity tracking: stores, locations, events with status (open/closed) and attributes
- Todo lists with geofence trigger metadata (alert when near location)
- Natural language updates ("the knife store in Osaka was closed today")

When memory is built (Platform MCP Phase 1, post-MVP), it will be a platform service,
not Shogun-internal.

## MCP — NOT in This Reboot

MCP integration is explicitly deferred. Do not build it.
Shogun uses direct REST calls to platform services.
Reason: Gemini uses Function Calling API, not MCP protocol. Bridging them
requires Option C (LLM gateway enhancement) which is scoped to the OpenRouter
planning session, not this reboot.

## Database

- Database: shogun_v1 on dbnode-01 (192.168.71.221)
- Existing roles: mcp_shogun (dormant), mcp_group (dormant)
- New schemas likely needed: expenses, itinerary, locations (check existing schema first)
- Any new table requires dba-agent task with approved plan

## Automations (Replacing n8n)

n8n is being decommissioned. Automation pattern going forward:
- Cron-based Python scripts
- Run on brainnode-01 (no Docker) or as svcnode-01 sidecar services
- Save output to database or filesystem

Planned automations (deferred post-MVP, not for reboot):
- YouTube monitoring (keyword alerts, transcript download)
- RSS feed reader
- Calendar sync

## Future Services (Not for Reboot — Backlog)

- Translation: Japanese ↔ English written and spoken (Google Translate + Speech API)
  — requires Google API auth setup (separate conversation)
- Google Maps itinerary pins: per-day travel pins with notes
- Garmin fitness data: step counts per location (low priority, own project)
- OpenRouter as platform service: model selection per application (own planning session)

## Open Questions for the Shogun Session

1. What does the existing Shogun codebase look like? Read it before designing.
2. Which schemas already exist in shogun_v1? Run a schema audit before any DDL.
3. What Telegram bot token and config is already set up?
4. Google Places routing: platform_v1.places vs shogun_v1.places — still unresolved.
   Must be decided before any Places-related feature is built.

## References

- Platform MCP plan: `outputs/planning/mcp-infrastructure-plan.md`
- Platform planning state: `outputs/planning/planning-state.md`
- Platform rules: `.claude/rules/01-infrastructure.md` through `05-database.md`
- Platform services index: `.claude/services/_index.md`
