# IbbyTech Platform — Service Index

**Before building any new capability, check this index first.**
If the service exists here, consume it. Do not duplicate it.

All services run on `svcnode-01` (192.168.71.220) behind Traefik
unless otherwise noted.

---

## Active Services

| Service | FQDN | Purpose | Doc |
|:---|:---|:---|:---|
| Google Places | `places.platform.ibbytech.com` | Location search, place details, ratings | [google-places.md](google-places.md) |
| Telegram Bot | `telegram.platform.ibbytech.com` | Bot messaging, notifications, commands | [telegram-bot.md](telegram-bot.md) |
| LLM Gateway | `llm.platform.ibbytech.com` | Unified LLM API access (multi-provider) | [llm-gateway.md](llm-gateway.md) |
| Scraper | `scrape.platform.ibbytech.com` | Web scraping, crawling, URL mapping, LLM extraction; auto-persists + embeds to Postgres (pgvector). Depends on Firecrawl via host port 3002 (not platform_net) — see `/opt/firecrawl` | [scraper.md](scraper.md) |
| Reddit Gateway | `reddit.platform.ibbytech.com` | Read Reddit posts/comments via public JSON API (no credentials). Unicode/kanji search. Persists to platform_v1.reddit with pgvector embeddings. Scheduled feeds. | [reddit-gateway.md](reddit-gateway.md) |
| Valkey | `valkey.platform.ibbytech.com:6379` | Shared in-memory key/value store (Redis-protocol). Session state, conversation context, caching. TCP service — not HTTP. Auth required. | [valkey.md](valkey.md) |
| Loki | Internal — `192.168.71.220:3100` | Centralized log aggregation — NODE_ONLY: deployed at `/opt/logstack/`, not tracked in platform git repo | [loki.md](loki.md) |
| Grafana | Internal — `192.168.71.220:3000` | Observability dashboards — NODE_ONLY: deployed at `/opt/logstack/`, not tracked in platform git repo | [grafana.md](grafana.md) |

## Services Recently Added (Docs Pending)

| Service | Deployed | Notes |
|:---|:---|:---|

## Planned Services

| Service | Purpose | Target Node |
|:---|:---|:---|
| *(add here)* | | |

---

## Non-Platform Tools

Tools running on platform nodes that are NOT shared services and NOT consumed
by other services or agents. Listed for inventory completeness only.

| Tool | Node | Purpose | Notes |
|:---|:---|:---|:---|
| Focalboard | svcnode-01 | Self-hosted project management / kanban board (Mattermost OSS) | Standalone UI — not behind Traefik, not API-consumed |

---

## Adding a New Service

Run `/register-service` after any deployment to svcnode-01.
The command generates the service doc and updates this index automatically.

Do not add services manually to this index without a corresponding service doc.
