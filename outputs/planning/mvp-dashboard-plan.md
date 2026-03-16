# Plan: MVP Platform Testing Dashboard
Date: 2026-03-07
Status: Approved — Ready for Execution

## Objective
A localhost:8000 web application running on the laptop that exercises all major
platform services (LLM gateway, scraper, Google Places, document RAG pipeline)
in one place. Primary purpose: validate that platform resources are working
and data is flowing correctly. Secondary purpose: serves as the foundation
codebase for Project Shogun (MVP 2).

## Scope
**Included:**
- FastAPI app running on laptop, accessible at http://localhost:8000
- 5 UI sections (tabbed single page): Dashboard, Documents, RAG Chat, Scraper, Places
- RAG pipeline: upload → extract → chunk → embed → store → query → display with source chunks
- Service health dashboard: live HTTP ping of each platform service
- Scraper integration: paste URL → cleaned text returned
- Google Places: live API search + display of cached database results
- Local SQLite for embedding storage (MVP, throwaway)

**Explicitly out of scope:**
- No authentication (internal laptop use only)
- No deployment to svcnode-01 (localhost only)
- No brainnode-01 involvement (deferred to MVP 2)
- No Cloudflare or external exposure
- No platform_v1 schema changes (SQLite for now)
- No mobile optimization

## Current State
Platform services are deployed and accessible on the 192.168.71.x internal
network from the laptop. Service URLs reachable by domain name or IP:
- svcnode-01.ibbytech.com (192.168.71.220)
- Traefik-routed services: places.platform.ibbytech.com, etc.
- LLM gateway URL needs confirmation from services/_index.md before execution

## Proposed Approach

### Application Structure
```
C:\git\work\platform\tools\dashboard\
  app.py              — FastAPI app, route handlers
  rag.py              — Document ingestion and RAG query pipeline
  services.py         — Platform service clients (health, scraper, places, LLM)
  requirements.txt    — All Python dependencies
  .env.example        — Required environment variables (no values)
  templates\
    index.html        — Single-page tabbed UI (Jinja2 + vanilla JS)
  data\
    embeddings.db     — SQLite database (gitignored, local only)
    uploads\          — Temporary upload storage (gitignored)
```

### RAG Pipeline Detail
1. Upload: User drops PDF/Word/TXT/MD via browser form
2. Extract: pdfplumber (PDF), python-docx (Word), native read (TXT/MD)
3. Chunk: Split into ~500-token paragraphs with 50-token overlap
4. Embed: Call OpenAI text-embedding-3-small API (OPENAI_API_KEY from .env)
5. Store: SQLite table — doc_id, filename, chunk_index, chunk_text, embedding (blob)
6. Query: Embed the question → cosine similarity → retrieve top 5 chunks
7. Completion: Send question + top 5 chunks to LLM gateway → stream response
8. Display: Answer on left, source chunks panel on right (so you can see evidence)

### UI Sections
**Tab 1 — Dashboard**
- Grid of service status cards (LLM gateway, scraper, Google Places, Telegram, Reddit)
- Each card: service name, status (green/red), last response time (ms), last checked
- Auto-refresh every 30 seconds + manual refresh button

**Tab 2 — Documents**
- File drop zone (PDF, Word, TXT, MD)
- Upload progress and extraction status
- List of indexed documents with chunk count and embedding status
- Delete document (removes from SQLite)

**Tab 3 — RAG Chat**
- Conversation thread (maintains context within browser session)
- Shows which documents are in the index
- After each answer: collapsible "Source Chunks" panel showing retrieved text + similarity scores
- Clear indicator when answer is grounded in documents vs. LLM general knowledge

**Tab 4 — Scraper**
- URL input field + Submit
- Returns: cleaned summary (from LLM) + raw scraped text (collapsible)
- Demonstrates: scraper → LLM pipeline is working

**Tab 5 — Places**
- Search input + Submit
- Live results: calls Google Places gateway → displays name, address, rating, type
- Cached results: queries shogun_v1.places (existing data) for same search term
- Side-by-side display makes it easy to see live vs. cached

## Phases

### Phase 0: Prerequisites Validation (run first — all green before any dashboard code)
Goal: Confirm every platform resource the dashboard depends on is reachable and functional from the laptop before writing a single line of dashboard code.
Entry criteria: Python environment set up, .env configured, devops-agent SSH key accessible
Deliverables:
- `tools/dashboard/validate_connectivity.py` — network and port reachability for all services
- `tools/dashboard/validate_llm_gateway.py` — LLM gateway API and container audit
- Console output: color-coded pass/fail table for every check
Exit criteria: All checks green. Any red finding is investigated and resolved before Phase 1 begins. Do not proceed with dashboard build if LLM gateway is red.
Complexity: Low
Dependencies: devops-agent SSH key at ~/.ssh/devops-agent_ed25519_clean

**validate_connectivity.py checks:**
| Check | Method | Pass Condition |
|-------|--------|----------------|
| svcnode-01.ibbytech.com | HTTP GET | 200 or any response (not connection refused) |
| LLM gateway URL | HTTP GET | Reachable (URL to be confirmed from services/_index.md) |
| Scraper service URL | HTTP GET /health or / | Reachable |
| Google Places gateway | HTTP GET | Reachable |
| Telegram gateway | HTTP GET | Reachable |
| Reddit gateway | HTTP GET | Reachable |
| dbnode-01 port 5432 | TCP connect | Port open from laptop IP |

**validate_llm_gateway.py checks:**
Part A — From laptop (HTTP):
| Check | Method | Pass Condition |
|-------|--------|----------------|
| Basic reachability | HTTP GET / | Any response |
| Completion endpoint | POST /v1/chat/completions | Returns valid response with content |
| Streaming support | POST with stream=True | Receives streamed tokens |
| Embedding endpoint | POST /v1/embeddings | 200 response (or document as not supported) |
| Model reported | Parse completion response | Log model name for visibility |

Part B — Via SSH as devops-agent (container inspection):
| Check | Command | Pass Condition |
|-------|---------|----------------|
| Container running | docker ps \| grep llm-gateway | Container present and Up |
| Environment vars | docker inspect (env) | OPENAI_API_KEY present (value masked) |
| Anthropic key | docker inspect (env) | ANTHROPIC_API_KEY present if expected (value masked) |
| Recent logs | docker logs --tail 50 | No ERROR or FATAL entries |

### Phase 1: Core RAG (target: first half of day)
Goal: Upload a document and get a grounded answer in the browser
Entry criteria: Python environment set up, .env configured with API keys
Deliverables:
- FastAPI app starts at localhost:8000
- Document upload and extraction working
- Embeddings generated and stored in SQLite
- RAG query returns answer + visible source chunks
Exit criteria: Upload a PDF, ask a question about it, see the answer cite content from the doc
Complexity: Medium
Dependencies: OPENAI_API_KEY in .env, LLM gateway URL confirmed

### Phase 2: Service Dashboard + Scraper + Places (target: second half of day)
Goal: All 5 UI tabs functional
Entry criteria: Phase 1 complete
Deliverables:
- Dashboard tab showing live health of all platform services
- Scraper tab returning cleaned summaries
- Places tab showing live + cached results
Exit criteria: All tabs return real data without errors
Complexity: Low (mostly HTTP calls to existing services)
Dependencies: Phase 1 complete, service URLs confirmed

## Dependencies
- OPENAI_API_KEY — must be in .env before execution
- LLM gateway internal URL — confirm from .claude/services/_index.md before coding
- Scraper service URL — confirm from .claude/services/_index.md
- Google Places gateway URL — places.platform.ibbytech.com (known)
- shogun_v1 database connection — for Places cached results tab
  (need PGPASSWORD/connection string for laptop → dbnode-01 connection)

## Risks
| Risk | Likelihood | Impact | Category | Mitigation | Status |
|------|------------|--------|----------|------------|--------|
| LLM gateway doesn't expose streaming from outside Docker network | Medium | Medium | Architecture | Test simple HTTP call first; fall back to non-streaming if needed | Open |
| OpenAI embedding API latency makes upload feel slow | Low | Low | Operational | Chunk async, show progress indicator | Open |
| SQLite cosine similarity requires numpy — no pgvector on laptop | Low | Low | Dependency | Use numpy for cosine sim; already implicit in openai package | Open |
| shogun_v1 Places connection from laptop requires pg firewall rule | Medium | Low | Operational | Test connection early; fall back to live-only Places if blocked | Open |

## Open Items
- Confirm LLM gateway URL accessible from laptop (check services/_index.md)
- Confirm scraper service external URL
- Verify laptop can connect to shogun_v1 on dbnode-01 (PostgreSQL port 5432 open to laptop IP)

## Out of Scope
- Authentication (MVP 2)
- brainnode-01 file storage (MVP 2)
- platform_v1 pgvector migration (MVP 2)
- Mobile UI (MVP 2)
- Cloudflare (production only)
