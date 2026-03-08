# Planning State — IbbyTech Platform
Last updated: 2026-03-07

## Project Summary
IbbyTech home lab enterprise-lite platform. Primary proving ground application
is Project Shogun — an AI travel concierge service. Platform services (scraper,
Google Places, LLM gateway, Telegram, Reddit) are deployed on svcnode-01 and
built here first for reuse in future projects. mltrader (ML trading bot using
10-year bond futures data) is a planned future project, not yet started.

## Active Work
| Item | Description | Phase | Status | Last Updated |
|------|-------------|-------|--------|--------------|
| Scraper service | Web scraper backed by Firecrawl on svcnode-01 | Production | Complete | 2026-03-05 |
| Google Places gateway | Places search and storage | Production | Complete | 2026-03-06 |
| LLM gateway | LLM completion service on svcnode-01 | Production | Complete | 2026-03-01 |
| Reddit gateway | Deployed 2026-03-02 | Production | Complete — docs pending | 2026-03-02 |
| MVP Testing Dashboard | localhost:8000 platform test harness | Phase 0 — Validation | Approved — start with validate_connectivity.py + validate_llm_gateway.py | 2026-03-07 |

## Open Decisions
- **Google Places routing:** `platform_v1.places` vs `shogun_v1.places` — canonical dataset ownership unresolved. Must be decided before Shogun build begins.
- **Web frontend for Project Shogun (MVP 2):** Full application deferred. Will be built on top of the MVP Testing Dashboard once validated.
- **brainnode-01 document storage:** Deferred to MVP 2. MVP 1 uses local SQLite on laptop.
- **Authentication:** No auth in MVP 1. Future production plan: Cloudflare + Google OAuth for Project Shogun.

## Technology Registry
| Technology | Role | Rationale | Date |
|------------|------|-----------|------|
| Traefik v3 | Reverse proxy on svcnode-01 | Label-based Docker service discovery, automatic cert management — selected over nginx | 2026-03-01 |
| PostgreSQL 17 | Primary database on dbnode-01 | Enterprise-grade, pgvector support | 2026-02-15 |
| Docker Compose | Service orchestration | Standard for multi-service deployment on svcnode-01 | 2026-02-15 |
| Firecrawl | Web scraping engine | Managed service with JS rendering — selected over raw BeautifulSoup | 2026-03-04 |
| Python 3.x | Service runtime | Default for platform services | 2026-02-15 |
| FastAPI | Web framework for MVP dashboard | Python-first, async, serves Jinja2 templates — selected for localhost MVP | 2026-03-07 |
| pdfplumber | PDF text extraction | Cleanest API for text + layout extraction, pure Python — approved for MVP dashboard | 2026-03-07 |
| python-docx | Word document extraction | De facto standard for .docx in Python — approved for MVP dashboard | 2026-03-07 |
| SQLite | Local embedding store (MVP) | Throwaway MVP storage — upgrade path to platform_v1 pgvector in MVP 2 | 2026-03-07 |
| OpenAI embeddings | text-embedding-3-small via API | Consistent with scraper service approach, key already in platform .env | 2026-03-07 |

## Decision Log

### Reverse Proxy Selection — 2026-03-01
- Capability need: Route HTTP traffic to multiple services on svcnode-01
- Options considered: nginx, Caddy, Traefik v3, HAProxy
- Decision: Traefik v3
- Reasoning: Label-based Docker service discovery, native Let's Encrypt, best fit for growing multi-service architecture
- Risk accepted: None significant

### Scraper Firecrawl Connection Pattern — 2026-03-06
- Capability need: Scraper service must reach Firecrawl across separate Docker networks
- Options considered: Join firecrawl to platform_net, host.docker.internal, direct IP
- Decision: host.docker.internal:3002 (HOST_IP pattern)
- Reasoning: Firecrawl root-owned legacy service on separate network. Host routing avoids reconfiguration risk.
- Risk accepted: Host network dependency — if Firecrawl port changes, scraper .env must be updated

### MVP Dashboard Document Extraction Libraries — 2026-03-07
- Capability need: Extract text from PDF, Word, TXT, Markdown for RAG pipeline
- Options considered: pdfplumber vs PyMuPDF vs pypdf (PDF); python-docx is uncontested for Word
- Decision: pdfplumber + python-docx
- Reasoning: pdfplumber has cleanest text extraction API with no system dependencies; python-docx is the only viable option for .docx
- Risk accepted: None

### MVP Dashboard Embedding Storage — 2026-03-07
- Capability need: Store document embeddings for RAG query
- Options considered: platform_v1 pgvector on dbnode-01, local SQLite, in-memory
- Decision: Local SQLite for MVP 1
- Reasoning: Keep MVP fast to build and self-contained on laptop. No schema changes to platform_v1 needed for day-1 testing. Upgrade path to pgvector is documented.
- Risk accepted: SQLite is throwaway — embeddings will need to be re-generated when migrating to platform_v1 in MVP 2

### MVP Dashboard Phase 0 — Validation-First Approach — 2026-03-07
- Decision: Add Phase 0 (prerequisite validation scripts) before any dashboard code is written
- Reasoning: LLM gateway suspected not fully tested for external access. Discovering a broken gateway mid-build wastes the build day. All red findings must be resolved to green before Phase 1 begins.
- Scripts: validate_connectivity.py (network/port reachability), validate_llm_gateway.py (API + SSH container audit)
- Risk accepted: None — this reduces risk

### MVP Dashboard Frontend Technology — 2026-03-07
- Capability need: Simple web UI served from localhost:8000
- Options considered: FastAPI + Jinja2 + vanilla JS, Streamlit, Next.js
- Decision: FastAPI + Jinja2 templates + minimal vanilla JS (fetch for AJAX)
- Reasoning: Python-first, no build step, sufficient for testing harness scope. Streamlit rejected — known rewrite required since this becomes Shogun foundation. Next.js rejected — too heavy for a 1-day localhost tool.
- Risk accepted: None for MVP scope

## Backlog
- Reddit gateway service doc: Deployed 2026-03-02, still pending. Run /register-service.
- MCP architecture: mcp_shogun dormant on dbnode-01 — architecture decision needed
- brainnode-01 onboarding: No projects deployed yet. SSH key setup and git permissions needed before any service can be deployed there.
- mltrader project: New project under C:\git\work\mltrader — not started, planning not yet initiated

## Planning Documents
| Document | Path | Status |
|----------|------|--------|
| MVP Testing Dashboard Plan | outputs/planning/mvp-dashboard-plan.md | Approved — ready for execution |
