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
| Scraper | `scrape.platform.ibbytech.com` | Web scraping, crawling, URL mapping, LLM extraction; auto-persists + embeds to Postgres (pgvector) | [scraper.md](scraper.md) |
| Loki | Internal — `192.168.71.220:3100` | Centralized log aggregation | [loki.md](loki.md) |
| Grafana | Internal — `192.168.71.220:3000` | Observability dashboards | [grafana.md](grafana.md) |

## Services Recently Added (Docs Pending)

| Service | Deployed | Notes |
|:---|:---|:---|
| Reddit API | 2026-03-02 | Reddit gateway — doc needed, run `/register-service` |

## Planned Services

| Service | Purpose | Target Node |
|:---|:---|:---|
| *(add here)* | | |

---

## Adding a New Service

Run `/register-service` after any deployment to svcnode-01.
The command generates the service doc and updates this index automatically.

Do not add services manually to this index without a corresponding service doc.
