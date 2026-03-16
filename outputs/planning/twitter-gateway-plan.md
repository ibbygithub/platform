# Plan: Twitter/X Gateway
Date: 2026-03-10
Status: Draft — backlogged, not yet in execution

## Objective

Build a platform-wide read gateway for Twitter/X content. Any platform service
or AI agent can search and retrieve tweets without interacting with Twitter's
paid API. All retrieved content is persisted to `platform_v1.twitter` with
pgvector embeddings for semantic similarity search.

Follows the same architectural pattern as the Reddit gateway, with one key
difference: Twitter does not expose a free public API. Authentication via real
Twitter accounts (free tier) is required. This is a structural difference from
Reddit, accepted as the cost of Twitter data access without paying $100/month.

## Scope

**Included:**
- Keyword/hashtag search over Twitter (returns tweets matching query)
- User timeline retrieval
- Single tweet + reply thread fetch
- Semantic search over stored tweets (pgvector, no live Twitter call)
- Scheduled feed collection (same APScheduler pattern as Reddit gateway)
- Feed CRUD API
- Storage in platform_v1.twitter schema with embeddings
- Traefik routing on platform_net

**Explicitly excluded:**
- Write operations (posting, replying, liking) — read-only by design
- Twitter media (images, video) — text content only
- Trending topics endpoint — low value for Shogun use case
- Real-time streaming — not viable without paid API

## Key Difference from Reddit Gateway

The Reddit gateway is credential-free because Reddit deliberately allows
unauthenticated read access via their public JSON API.

Twitter/X has systematically closed all free access paths since 2023:
- Free API tier eliminated February 2023
- Guest token system heavily restricted through 2023–2024
- Search endpoints now require authenticated sessions
- Paid API starts at $100/month (Basic tier)

Every viable approach without paying requires real Twitter accounts.
This is accepted. The operational discipline (rate limits, account pooling)
mitigates the ban risk.

## Current State

Platform services operational on svcnode-01:
- Reddit gateway (credential-free, public JSON API, platform_v1.reddit schema)
- Scraper, LLM gateway, Google Places, Telegram — all running
- platform_v1 database on dbnode-01 — reddit schema in place, pattern established

The Twitter gateway follows the Reddit gateway pattern in all infrastructure
decisions. The divergence is authentication model only.

## Option Analysis

### Option 1: twscrape — RECOMMENDED
Python library that authenticates against Twitter's internal mobile GraphQL API
using real Twitter accounts (free tier).

Strengths:
- Most complete API surface of any free approach (search, timeline, user lookup)
- Python-native, fits platform runtime
- Uses same endpoints Twitter's mobile app uses — hardest to block without
  breaking their own app
- Supports account pooling (multiple accounts = more throughput)
- Returns structured data, not HTML to parse
- Most mature and actively maintained of the available options

Weaknesses:
- Requires real Twitter accounts — not credential-free like Reddit
- Account bans when scraped aggressively or detected
- Internal API endpoints break periodically when Twitter updates their app
- Rate limits apply per account (~50 searches/15 min per account)
- Against Twitter ToS — no ambiguity here

### Option 2: twikit
Newer Python library using same internal Twitter API approach. Async-first design.

Strengths: More active development cadence 2025-2026, async-native (better FastAPI fit)
Weaknesses: Less mature than twscrape, smaller community, same fundamental risks
Verdict: Valid drop-in alternative if twscrape fails Phase 0 validation.

### Option 3: Self-hosted Nitter → scrape own instance
Nitter is an open-source Twitter frontend. Scrape Nitter instead of Twitter directly.

Verdict: Do not recommend. Nitter relies on Twitter guest tokens which have been
heavily blocked since 2023. Search is broken on most instances. Development stalled.
Adds complexity (two services) with no reliability gain over twscrape.

### Option 4: Playwright browser automation
Drive a real Chromium browser against twitter.com.

Verdict: Do not recommend as primary approach. 500MB+ memory per browser instance,
seconds per request latency, fragile to UI changes, still requires a logged-in account.
Unsuitable for synchronous API backend.

### Option 5: Third-party scrapers (RapidAPI, Apify, etc.)
Proxy scraping services with their own account pools.

Verdict: Excluded — these have billing models that violate the "no paid service"
constraint, and data flows through a third party.

## Recommended Approach

**twscrape with a pool of 2–3 dedicated Twitter accounts (free tier).**

Account pool credentials stored in `.env` as `TWITTER_ACCOUNT_1`, `TWITTER_ACCOUNT_2`, etc.
twscrape manages session state (cookies/tokens) in local SQLite inside the container.
Health endpoint reports per-account status and ban detection.

Rate discipline is stricter than Reddit gateway — 20 req/min across the pool
(not per account). Exponential backoff on 429s. Feed scheduler runs daily, not hourly.

## Architecture

```
twitter-gateway (svcnode-01, port 8083, platform_net)
├── FastAPI app
│   ├── POST /v1/twitter/search          — keyword/hashtag search
│   ├── POST /v1/twitter/user/timeline   — user's recent tweets
│   ├── GET  /v1/twitter/tweet/{id}      — single tweet + replies
│   ├── POST /v1/twitter/saved/search    — semantic search (pgvector only)
│   ├── POST /v1/twitter/feeds           — register scheduled feed
│   ├── GET  /v1/twitter/feeds           — list feeds
│   ├── DELETE /v1/twitter/feeds/{id}    — remove feed
│   └── GET  /health                     — status + account pool health
│
├── twitter_client.py  — twscrape wrapper, account pool, rate limiter
├── db.py              — psycopg2, upsert tweets/users, semantic search
├── embeddings.py      — LLM gateway integration (mirrors reddit/scraper pattern)
├── scheduler.py       — APScheduler feed runner
└── schema.sql         — platform_v1.twitter schema
```

Database: platform_v1, schema twitter
Tables: twitter_tweets, twitter_users, twitter_feeds, twitter_query_cache
Embeddings: pgvector ivfflat on tweet text embeddings (lists=50)
Network: platform_net, Traefik FQDN twitter.platform.ibbytech.com
App user: twitter_app (scoped to twitter schema — same pattern as reddit_app)

## Phases

### Phase 0 — Account Setup and twscrape Validation (pre-build, laptop only)
Goal: Confirm twscrape works with real accounts before committing build effort.
Entry criteria: 2–3 dedicated Twitter accounts created (free tier, non-personal
               identity, dedicated email addresses not linked to personal use)
Deliverables:
  - Accounts created and verified
  - Local twscrape test: authenticate, run one search, inspect result structure
  - Decision confirmed: proceed with twscrape or pivot to twikit
Exit criteria: At least one authenticated search returning structured tweet data
Complexity: Low
Note: Laptop-level validation only. No infrastructure changes.

### Phase 1 — Schema and Database Provisioning (dbnode-01)
Goal: platform_v1.twitter schema ready to receive tweets
Entry criteria: Phase 0 complete, tweet data structure confirmed
Deliverables:
  - schema.sql: twitter_tweets, twitter_users, twitter_feeds, twitter_query_cache
  - pgvector ivfflat indexes on tweet embedding columns
  - twitter_app role with scoped permissions (same pattern as reddit_app)
  - pg_hba.conf entry for 192.168.71.220
  - dba-agent executes schema, evidence report written
Exit criteria: twitter_app can connect and INSERT; tables confirmed via \dt
Complexity: Low
Persona: dba-agent

### Phase 2 — Core Service Build (laptop → svcnode-01)
Goal: Container running on platform_net, search and timeline endpoints
      functional, tweets persisted with embeddings
Entry criteria: Phase 1 complete
Deliverables:
  - twitter_client.py, db.py, embeddings.py, app.py, schema.sql
  - Dockerfile, docker-compose.yml (platform_net, Traefik labels)
  - .env.example with account pool structure documented
  - Container deployed to svcnode-01 via git push
Exit criteria: GET /health shows accounts active; POST /v1/twitter/search
              returns tweets persisted to platform_v1.twitter with embeddings
Complexity: Medium
Persona: devops-agent (deploy), dba-agent (verify DB writes)

### Phase 3 — Feed Scheduler and Semantic Search
Goal: Scheduled feeds collecting; semantic search over stored tweets working
Entry criteria: Phase 2 complete, tweets in database
Deliverables:
  - scheduler.py (APScheduler, feed-based collection)
  - POST /v1/twitter/saved/search (pgvector similarity)
  - Feed CRUD endpoints functional
  - Shogun seed feeds registered (Japan travel/food — terms TBD, see Open Items)
Exit criteria: Scheduler fires on interval; saved/search returns results with
              similarity scores; at least one feed run confirmed
Complexity: Medium

### Phase 4 — Service Documentation and Registration
Goal: Twitter gateway is a first-class registered platform service
Entry criteria: Phase 3 complete, all endpoints validated
Deliverables:
  - .claude/services/twitter-gateway.md
  - .claude/services/_index.md updated
  - outputs/validation/ evidence report
Exit criteria: Service doc matches reddit-gateway.md standard
Complexity: Low

## Dependencies

- twscrape library (Python, open source — must validate in Docker in Phase 0)
- 2–3 dedicated Twitter accounts (free tier, non-personal identity)
- LLM gateway (for embeddings — already running on platform_net)
- platform_v1 database on dbnode-01 (schema provisioning via dba-agent)
- Traefik on svcnode-01 (already running)

## Risks

| Risk | Likelihood | Impact | Mitigation |
|:---|:---|:---|:---|
| Twitter internal API endpoints change, breaking twscrape | Medium | High | Version-pin twscrape; monitor upstream; twikit is drop-in alternative |
| Scraper accounts get banned | Medium | Medium | Account pool (3 accounts); conservative rate limits; health endpoint monitors ban status |
| Twitter implements stronger ML bot detection | Low-Medium | High | Accept — no mitigation. Structural risk of this approach. |
| twscrape goes unmaintained | Low | High | twikit is viable drop-in; migration straightforward |
| Search result quality degrades silently | Medium | Medium | Health endpoint tracks result count baseline |

## Open Items

1. **Account identity policy:** Dedicated accounts must not link to personal
   identity. Confirm process for creating non-personal accounts before Phase 0.

2. **Shogun seed feed content:** Target hashtags and search terms for initial
   feeds. Equivalent of Reddit's Japan/ramen subreddits. Candidates:
   `#japan`, `#tokyo`, `#ramen`, Japanese-language terms like `ラーメン おすすめ`.
   Decide before Phase 3 execution.

## Out of Scope

- Twitter write operations (post, reply, like, retweet)
- Twitter media content (images, video metadata)
- Real-time tweet streaming
- Twitter paid API integration (explicitly excluded)
- Trending topics
