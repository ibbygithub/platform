# Platform Architecture

## Lab Topology

```
Windows 11 laptop (dev)
    │  git push → github.com/ibbygithub/platform
    ▼
GitHub
    │
    ├── git pull → svcnode-01   (Docker host)
    ├── git pull → brainnode-01 (apps, cron, MCP)
    └──  (reads only)  dbnode-01 (PostgreSQL + pgvector)
```

## Network Topology

```
internet / Cloudflare Tunnel (future)
        │
        ▼
  Traefik (svcnode-01, ports 80/443)
        │ platform_net (Docker bridge)
        ├── telegram-gateway   :3000  → telegram.platform.ibbytech.com
        ├── places-google      :8081  → places.platform.ibbytech.com
        ├── llm-gateway        :8080  → llm.platform.ibbytech.com
        ├── reddit-gateway     :8082  → reddit.platform.ibbytech.com
        └── scraper-api        :8083  → scrape.platform.ibbytech.com
                │ scraper_internal (isolated)
                ├── firecrawl-api  :3002
                ├── firecrawl-worker
                └── scraper-redis  :6379

dbnode-01 (separate host)
  ├── PostgreSQL :5432
  │     └── platform_v1 database
  │           └── places schema (google_places, google_place_snapshots)
  └── pgvector extension (for future embedding storage)
```

## Service Responsibilities

### Traefik
- TLS termination for `*.platform.ibbytech.com`
- Routes inbound HTTPS to the correct container via Docker labels
- Creates `platform_net` bridge network (all services join this)

### Telegram Gateway
- Polls Telegram API (current) or receives webhooks (future, when Cloudflare is live)
- Wraps every Telegram event in a standard JSON envelope
- Forwards to `UPSTREAM_URL` — whatever application is consuming events
- Returns upstream `reply_text` back to the chat if provided
- Zero application logic; pure ingress

### Google Places
- Wraps Google Places API (New) text search and nearby search
- Requires a geographic anchor (lat/lng) on every request
- Environment-configurable field masks, region, language, and radius defaults
- PostgreSQL schema available for durable place storage (app-layer write not yet implemented)

### LLM Gateway
- Unified chat and embeddings API across OpenAI, Google Gemini, and Anthropic Claude
- Provider and model selectable per request or via environment defaults
- Normalizes provider-specific response shapes into a consistent output format
- Note: Anthropic does not offer an embeddings API

### Reddit Gateway
- Read-only Reddit API wrapper using PRAW
- Script-app OAuth (no user authorization flow required)
- Supports post search, subreddit browsing, and post+comment retrieval

### Scraper
- Self-hosted Firecrawl handles actual scraping and crawling
- `scraper-api` wrapper provides a platform-consistent interface
- Firecrawl and Redis are isolated on `scraper_internal` — not exposed to `platform_net`
- Supports single-page scrape, multi-page crawl, and URL discovery (map)

## Design Principles

**MCP-style service boundaries.** Each service is a single-purpose HTTP API. No shared libraries. No in-process coupling. Services communicate over the network.

**Environment-driven configuration.** All secrets and tunables come from `.env` files on the host. `.env` is gitignored; `.env.example` is the contract.

**Traefik as the single entry point.** All external traffic enters through Traefik. Services are not bound to host ports (except Traefik itself). Internal service-to-service calls go over `platform_net` by container name.

**Database on dbnode-01.** Platform services connect to the existing PostgreSQL server. No per-service databases in Docker. Schema per service.

**Polling first, webhook later.** Telegram gateway defaults to polling mode (works on LAN). When Cloudflare Tunnel is configured, flip `TELEGRAM_MODE=webhook` and set `WEBHOOK_DOMAIN`.

## Deployment Path

```bash
# On svcnode-01:

# 1. Clone once
git clone git@github.com:ibbygithub/platform.git /opt/git/work/platform
cd /opt/git/work/platform

# 2. Start Traefik (creates platform_net)
cd infra/compose
docker compose -f docker-compose.infra.yml up -d

# 3. Start each service
cd /opt/git/work/platform/services/telegram-gateway
cp .env.example .env && vim .env    # fill in credentials
docker compose up --build -d

# Repeat for each service directory.

# 4. Update a service
cd /opt/git/work/platform
git pull origin main
cd services/<service>
docker compose up --build -d
```

## Adding a New Service

1. Create `services/<name>/`
2. Add `app.py` (or `gateway.js`), `Dockerfile`, `docker-compose.yml`, `.env.example`, `README.md`
3. In `docker-compose.yml`:
   - Join `platform_net` (external)
   - Add Traefik labels with `<name>.platform.ibbytech.com`
4. Push and deploy

## Cloudflare Tunnel (Future)

When ready:
1. Install `cloudflared` on svcnode-01
2. Create a Cloudflare Tunnel pointing to `http://localhost:80` (Traefik)
3. Add DNS CNAME records for each service FQDN → tunnel hostname
4. For Telegram: set `TELEGRAM_MODE=webhook`, `WEBHOOK_DOMAIN=https://telegram.platform.ibbytech.com`
5. Register the webhook: `curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://telegram.platform.ibbytech.com/webhook"`
