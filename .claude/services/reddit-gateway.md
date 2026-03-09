# Service: Reddit Gateway

**Version:** 2.0.0
**Node:** svcnode-01
**FQDN:** `reddit.platform.ibbytech.com`
**Container:** `platform-reddit-gateway`
**Port (internal):** 8082
**Deploy path:** `/opt/git/work/platform/services/reddit-gateway/`
**Deployed:** 2026-03-08
**Persona:** devops-agent

---

## Purpose

Platform-wide read gateway for Reddit content. Any platform service or AI agent
can search and read Reddit posts and comments without Reddit API credentials.
All retrieved content is persisted to `platform_v1.reddit` with pgvector embeddings
for semantic similarity search.

No OAuth credentials required — uses Reddit's public JSON API.

---

## Auth

None. Open on `platform_net` — any container on the network can call it.

---

## Endpoints

| Method | Path | Description |
|:---|:---|:---|
| GET | `/health` | Status, DB connectivity, config summary |
| POST | `/v1/reddit/search` | Search posts by keyword. Unicode/kanji supported. |
| POST | `/v1/reddit/subreddit/posts` | Browse subreddit listings (hot/new/top/rising) |
| GET | `/v1/reddit/post/{id}` | Fetch post + comments. Both persisted with embeddings. |
| GET | `/v1/reddit/subreddit/{name}/info` | Subreddit metadata |
| POST | `/v1/reddit/saved/search` | Semantic search over stored posts (pgvector, no Reddit call) |
| POST | `/v1/reddit/feeds` | Register a scheduled collection feed |
| GET | `/v1/reddit/feeds` | List all feeds |
| DELETE | `/v1/reddit/feeds/{id}` | Remove a feed |

---

## Request examples

**Search (kanji):**
```json
POST /v1/reddit/search
{"query": "ラーメン", "sort": "relevance", "time_filter": "all", "limit": 25}
```

**Search (English, scoped to subreddit):**
```json
POST /v1/reddit/search
{"query": "ramen hidden gem", "subreddit": "japan", "sort": "top", "time_filter": "year", "limit": 10}
```

**Semantic search (saved posts only):**
```json
POST /v1/reddit/saved/search
{"query": "local Japanese restaurant authentic not tourist", "limit": 10}
```

**Register feed:**
```json
POST /v1/reddit/feeds
{"subreddit": "ramen", "sort": "top", "time_filter": "week", "limit_per_run": 25, "cron_expr": "0 3 * * *"}
```

---

## Storage

**Database:** `platform_v1`
**Schema:** `reddit`
**User:** `reddit_app`

| Table | Contents |
|:---|:---|
| `reddit.posts` | Every retrieved post with pgvector embedding |
| `reddit.comments` | Top-level comments on explicitly fetched posts |
| `reddit.subreddits` | Subreddit metadata cache |
| `reddit.feeds` | Scheduled feed registry |
| `reddit.query_cache` | Cache tracking to avoid redundant Reddit calls |

---

## Rate limiting

Self-imposed 50 req/min token bucket. Scheduler spreads feed runs across 6-hour
intervals. On Reddit 429 responses, backs off 30 seconds and retries once.

---

## Scheduled feeds (Shogun seed — active at deployment)

| ID | Subreddit | Query | Cron |
|:---|:---|:---|:---|
| 1 | r/japan | ラーメン OR 居酒屋 OR レストラン | 0 2 * * * |
| 2 | r/japanlife | 食べ物 OR グルメ OR おすすめ | 0 2 * * * |
| 3 | r/tokyo | ramen OR izakaya OR restaurant | 0 3 * * * |
| 4 | r/ramen | (top posts, no query) | 0 3 * * * |

---

## Environment variables

| Variable | Required | Description |
|:---|:---|:---|
| `REDDIT_USER_AGENT` | Yes | Descriptive UA string with Reddit username |
| `PGPASSWORD` | Yes | reddit_app password — enables persistence |
| `PGHOST` | No | Default: `dbnode-01` |
| `PGDATABASE` | No | Default: `platform_v1` |
| `PGUSER` | No | Default: `reddit_app` |
| `LLM_GATEWAY_URL` | No | Default: `http://platform-llm-gateway:8080` |
| `CACHE_TTL_HOURS` | No | Default: `1.0` |
| `FEED_INTERVAL_HOURS` | No | Default: `6` |

---

## Known limitations

- `r/japan` and `r/japanlife` are primarily English-language communities — kanji
  queries return few results there. Use global search (no `subreddit` param) for
  Japanese-language content across all of Reddit.
- Comment embeddings are only generated when a specific post is fetched via
  `GET /v1/reddit/post/{id}` — not during bulk feed collection (would require
  one request per post).
- Write operations (posting, commenting) not implemented — read-only by design.
  If Reddit API access ticket is approved, OAuth credentials can be added as an
  upgrade path.
