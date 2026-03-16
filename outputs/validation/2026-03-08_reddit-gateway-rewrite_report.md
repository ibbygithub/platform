# Reddit Gateway v2 — Evidence Report
Date: 2026-03-08
Branch: feature/20260308-reddit-gateway-rewrite
Outcome: COMPLETED — all checks GREEN

---

## What Was Built

Replaced PRAW-based reddit-gateway (which required OAuth credentials Reddit no
longer issues self-service) with a credential-free implementation using Reddit's
public JSON API.

### New modules
- `reddit_client.py` — HTTP client with 50 req/min token-bucket rate limiter, 429 backoff
- `db.py` — psycopg2 helpers: upsert posts/comments/subreddits, cache tracking, semantic search
- `embeddings.py` — LLM Gateway integration (mirrors scraper pattern)
- `scheduler.py` — APScheduler background job, runs all enabled feeds every 6h
- `schema.sql` — platform_v1.reddit schema: 5 tables + pgvector ivfflat indexes

### Modified
- `app.py` — full rewrite: 9 endpoints, Loki logging, FastAPI lifespan for scheduler
- `requirements.txt` — removed praw, added psycopg2-binary, apscheduler, requests
- `Dockerfile` — updated to COPY *.py (multi-module)
- `docker-compose.yml` — added extra_hosts for dbnode-01 (matching scraper pattern)
- `.env.example` — rewritten for credential-free model

---

## Infrastructure Changes

### dbnode-01 (dba-agent)
- Created schema `reddit` in `platform_v1`
- Created role `reddit_app` with password
- Created tables: `reddit_posts`, `reddit_comments`, `reddit_subreddits`,
  `reddit_feeds`, `reddit_query_cache`
- Created ivfflat indexes on embedding columns (lists=50)
- Added pg_hba.conf entry: `reddit_app` from `192.168.71.220/32` scram-sha-256
- Reloaded PostgreSQL config

### svcnode-01 (devops-agent)
- Deployed container `platform-reddit-gateway` on platform_net
- Traefik labels configured for `reddit.platform.ibbytech.com`
- `.env` written with reddit_app credentials and User-Agent (by /u/anada-ibby)

---

## Smoke Test Results

| Test | Result |
|:---|:---|
| GET /health — db_connected | ✅ true |
| GET /health — persist_enabled | ✅ true |
| GET /health — user_agent | ✅ anada-ibby |
| POST /v1/reddit/search — English global | ✅ results returned |
| POST /v1/reddit/search — kanji global (ラーメン) | ✅ 5 posts returned |
| POST /v1/reddit/search — English scoped (r/japan) | ✅ 3 posts returned |
| POST /v1/reddit/search — kanji scoped (r/japan) | ✅ 0 — expected (r/japan is English) |
| POST /v1/reddit/subreddit/posts | ✅ r/ramen top/week — 3 posts |
| GET /v1/reddit/subreddit/ramen/info | ✅ 1,529,809 subscribers |
| POST /v1/reddit/saved/search | ✅ semantic results with similarity scores |
| Scheduler first run | ✅ fired 60s after startup |
| Feed 1 (r/japan kanji) | ✅ 0 posts (expected — English community) |
| Feed 2 (r/japanlife kanji) | ✅ 0 posts (expected — English community) |
| Feed 3 (r/tokyo english) | ✅ 5 posts saved |
| Feed 4 (r/ramen top) | ✅ 25 posts saved |

---

## Known Findings

### Kanji search scope
r/japan and r/japanlife are English-language communities — kanji queries correctly
return 0 results when scoped to those subreddits. Global kanji search works
correctly (5 Japanese-language posts returned for ラーメン).

For Shogun's local Japanese restaurant discovery use case, seed feeds should be
updated to either: (a) remove subreddit restriction on kanji queries, or (b) target
Japanese-language subreddits (e.g. r/newsokur, r/newsokunomoral). This is a
content/product decision, not a technical issue.

---

## Deliverables Checklist

- [x] reddit-gateway container running on svcnode-01
- [x] FQDN: reddit.platform.ibbytech.com (Traefik labels set)
- [x] platform_v1.reddit schema with pgvector
- [x] 4 Shogun seed feeds registered and active
- [x] .claude/services/reddit-gateway.md written
- [x] _index.md updated — Reddit Gateway moved from "pending" to "active"
- [x] Evidence report written
