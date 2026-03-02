# Reddit Gateway

Read-only HTTP wrapper around the Reddit API using PRAW. Search posts, retrieve subreddit content, and fetch individual posts with comments.

## Endpoints

| FQDN | Purpose |
|------|---------|
| `reddit.platform.ibbytech.com` | Reddit content gateway |

## Quick Start

1. Create a Reddit "script" app at https://www.reddit.com/prefs/apps
2. Fill in `.env`:
```bash
cp .env.example .env
docker compose up --build -d
curl https://reddit.platform.ibbytech.com/health
```

## API

### `GET /health`
```json
{ "ok": true, "credentials_set": true }
```

### `POST /v1/reddit/search`
Search posts by keyword, optionally scoped to a subreddit.
```json
{
  "query": "home lab networking",
  "subreddit": "homelab",
  "sort": "relevance",
  "time_filter": "month",
  "limit": 10
}
```

### `POST /v1/reddit/subreddit/posts`
Get hot / new / top / rising posts from a subreddit.
```json
{
  "subreddit": "homelab",
  "sort": "hot",
  "limit": 25
}
```

### `GET /v1/reddit/post/{post_id}?comment_limit=20`
Fetch a single post with top-level comments.

### `GET /v1/reddit/subreddit/{name}/info`
Get subscriber count, description, and metadata for a subreddit.

## Reddit App Setup

1. Go to https://www.reddit.com/prefs/apps → "create another app"
2. Choose **script**
3. Name it anything (e.g. `platform-reddit-gateway`)
4. Redirect URI: `http://localhost:8080` (not used for script apps)
5. Copy the client ID (under the app name) and client secret into `.env`
