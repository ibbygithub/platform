# Platform Reddit Gateway v2

Reads Reddit via the public JSON API — no OAuth credentials required.
All retrieved posts and comments are persisted to `platform_v1.reddit` schema
with pgvector embeddings for semantic search.

**FQDN:** `reddit.platform.ibbytech.com`

## Endpoints

| Method | Path | Description |
|:---|:---|:---|
| GET | `/health` | Service status, DB connectivity, config |
| POST | `/v1/reddit/search` | Search posts — Unicode/kanji supported |
| POST | `/v1/reddit/subreddit/posts` | Browse listings (hot/new/top/rising) |
| GET | `/v1/reddit/post/{id}` | Full post + comments, both persisted |
| GET | `/v1/reddit/subreddit/{name}/info` | Subreddit metadata |
| POST | `/v1/reddit/saved/search` | Semantic search over stored posts (pgvector) |
| POST | `/v1/reddit/feeds` | Register a scheduled collection feed |
| GET | `/v1/reddit/feeds` | List all feeds |
| DELETE | `/v1/reddit/feeds/{id}` | Remove a feed |

## Quick start

```bash
cp .env.example .env
# Edit .env: set REDDIT_USER_AGENT (your Reddit username), PGPASSWORD
docker compose up --build -d
curl http://localhost:8082/health
```

## Key design decisions

- **No credentials** — uses Reddit's public JSON API (`reddit.com/search.json` etc.)
- **Rate limit** — self-imposed 50 req/min token bucket, respecting Reddit's limits
- **Cache** — 1-hour Postgres-backed cache avoids repeat Reddit calls for same query
- **Embeddings** — all posts/comments embedded via LLM Gateway (text-embedding-3-small)
- **Scheduler** — APScheduler runs all enabled feeds every 6 hours (configurable via FEED_INTERVAL_HOURS)

## Kanji / Unicode search

Reddit's public JSON API accepts full Unicode. To find Japanese-language posts:
```json
POST /v1/reddit/search
{"query": "ラーメン", "sort": "relevance", "time_filter": "all"}
```

Note: r/japan and r/japanlife are primarily English-language communities.
Japanese-language posts appear in communities like r/newsokunomoral and
Japanese-specific subreddits. Global search (no subreddit restriction) returns
the widest set of Japanese-language results.

## Shogun seed feeds

| ID | Subreddit | Query | Schedule |
|:---|:---|:---|:---|
| 1 | r/japan | ラーメン OR 居酒屋 OR レストラン | daily 2am UTC |
| 2 | r/japanlife | 食べ物 OR グルメ OR おすすめ | daily 2am UTC |
| 3 | r/tokyo | ramen OR izakaya OR restaurant | daily 3am UTC |
| 4 | r/ramen | (top posts) | daily 3am UTC |

## Semantic search example

Search over posts already stored in Postgres — no Reddit call needed:
```json
POST /v1/reddit/saved/search
{"query": "best ramen Japan authentic local", "limit": 10}
```
