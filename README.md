# Platform Services

A standalone, home-lab enterprise platform. Each service is an independently deployable HTTP API. Any application — Shogun, future chatbots, MCP agents, cron jobs — calls these services over the network.

## Infrastructure

| Node | Role |
|------|------|
| `svcnode-01` | Docker host — runs all platform containers |
| `brainnode-01` | Apps, cron jobs, MCP services |
| `dbnode-01` | PostgreSQL + pgvector |

## Services

| Service | FQDN | Stack | Description |
|---------|------|-------|-------------|
| Traefik | `traefik.platform.ibbytech.com` | Traefik v3 | Reverse proxy, TLS termination |
| Telegram Gateway | `telegram.platform.ibbytech.com` | Node.js / Telegraf | Receives Telegram events, forwards as JSON |
| Google Places | `places.platform.ibbytech.com` | Python / Flask | Google Places API wrapper |
| LLM Gateway | `llm.platform.ibbytech.com` | Python / FastAPI | Chat + embeddings (OpenAI, Google, Anthropic) |
| Reddit Gateway | `reddit.platform.ibbytech.com` | Python / FastAPI | Reddit search and content retrieval |
| Scraper | `scrape.platform.ibbytech.com` | Python / FastAPI + Firecrawl | Web scraping and crawling |

## Quick Start

### 1. Start Traefik first (creates `platform_net`)

```bash
cd infra/compose
docker compose -f docker-compose.infra.yml up -d
```

### 2. Start any service

```bash
cd services/<service-name>
cp .env.example .env   # fill in credentials
docker compose up --build -d
```

### 3. Verify

```bash
curl https://<service>.platform.ibbytech.com/health
```

## Development Workflow

```
Windows laptop (develop)
    │  git push → github.com/ibbygithub/platform
    ▼
svcnode-01 (production)
    │  git pull origin main
    │  cd services/<service>
    ▼
    docker compose up --build -d
```

## Repository Layout

```
platform/
├── infra/
│   └── compose/
│       ├── docker-compose.infra.yml   # Traefik
│       └── traefik/
│           ├── dynamic/tls.yml
│           └── certs/                 # gitignored — manage manually
├── services/
│   ├── telegram-gateway/
│   ├── places-google/
│   ├── llm-gateway/
│   ├── reddit-gateway/
│   └── scraper/
└── docs/
    ├── ARCHITECTURE.md
    └── DEPLOYMENT.md
```

## Secrets

Real `.env` files are **never committed**. Each service directory contains `.env.example` with all required variables documented. Copy it to `.env` on each server and fill in credentials.

## Adding a New Service

1. Create `services/<name>/`
2. Add `app.py` (or `app.js`), `Dockerfile`, `docker-compose.yml`, `.env.example`, `README.md`
3. Join `platform_net` in `docker-compose.yml`
4. Add Traefik labels for `<name>.platform.ibbytech.com`
5. Start with `docker compose up --build -d`
