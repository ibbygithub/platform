-- Reddit Gateway schema for platform_v1
-- Run as: sudo -u postgres psql -d platform_v1 -f schema.sql
--
-- Rollback: DROP SCHEMA reddit CASCADE; DROP ROLE IF EXISTS reddit_app;
-- This schema is additive — no existing schemas are modified.

-- ── Role ──────────────────────────────────────────────────────────────────────
-- Password must be set by the DBA before the container starts.
-- Run after this script: ALTER ROLE reddit_app PASSWORD '<strong_password>';

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'reddit_app') THEN
    CREATE ROLE reddit_app WITH LOGIN PASSWORD 'CHANGEME_BEFORE_DEPLOY';
  END IF;
END $$;

-- ── Schema ────────────────────────────────────────────────────────────────────

CREATE SCHEMA IF NOT EXISTS reddit;

GRANT USAGE ON SCHEMA reddit TO reddit_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA reddit
  GRANT SELECT, INSERT, UPDATE ON TABLES TO reddit_app;

-- ── Tables ────────────────────────────────────────────────────────────────────

-- Subreddit metadata cache
CREATE TABLE IF NOT EXISTS reddit.subreddits (
  name          TEXT PRIMARY KEY,
  title         TEXT,
  description   TEXT,
  subscribers   BIGINT,
  active_users  INT,
  over18        BOOLEAN DEFAULT FALSE,
  created_utc   DOUBLE PRECISION,
  fetched_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Posts — one row per Reddit post ID
-- Upserted on every fetch: score and num_comments updated, embedding preserved
CREATE TABLE IF NOT EXISTS reddit.posts (
  id            TEXT PRIMARY KEY,        -- Reddit short ID e.g. "abc123"
  subreddit     TEXT NOT NULL,
  title         TEXT,
  selftext      TEXT,
  url           TEXT,
  author        TEXT,
  score         INT,
  upvote_ratio  REAL,
  num_comments  INT,
  permalink     TEXT,
  is_self       BOOLEAN,
  created_utc   DOUBLE PRECISION,
  fetched_at    TIMESTAMPTZ DEFAULT NOW(),
  query_used    TEXT,                     -- cache key of the query that retrieved this post
  embedding_json TEXT,                   -- JSON serialisation of the vector (backup)
  embedding     vector(1536)             -- pgvector column for cosine similarity search
);

CREATE INDEX IF NOT EXISTS posts_subreddit_idx  ON reddit.posts (subreddit);
CREATE INDEX IF NOT EXISTS posts_created_idx    ON reddit.posts (created_utc DESC);
CREATE INDEX IF NOT EXISTS posts_fetched_idx    ON reddit.posts (fetched_at DESC);
CREATE INDEX IF NOT EXISTS posts_query_idx      ON reddit.posts (query_used);
-- ivfflat index for approximate nearest-neighbour search
-- lists=50 is appropriate for up to ~500k rows; raise to 100 at ~1M rows
CREATE INDEX IF NOT EXISTS posts_embedding_idx  ON reddit.posts
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

-- Comments — top-level comments on fetched posts
CREATE TABLE IF NOT EXISTS reddit.comments (
  id            TEXT PRIMARY KEY,
  post_id       TEXT NOT NULL REFERENCES reddit.posts(id) ON DELETE CASCADE,
  author        TEXT,
  body          TEXT,
  score         INT,
  created_utc   DOUBLE PRECISION,
  fetched_at    TIMESTAMPTZ DEFAULT NOW(),
  embedding_json TEXT,
  embedding     vector(1536)
);

CREATE INDEX IF NOT EXISTS comments_post_idx       ON reddit.comments (post_id);
CREATE INDEX IF NOT EXISTS comments_embedding_idx  ON reddit.comments
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

-- Query result cache — tracks what was fetched when to avoid redundant Reddit calls
CREATE TABLE IF NOT EXISTS reddit.query_cache (
  cache_key       TEXT PRIMARY KEY,       -- SHA-256 of normalised query params (first 32 chars)
  last_fetched_at TIMESTAMPTZ DEFAULT NOW(),
  result_count    INT
);

-- Scheduled feed registry — managed via API, executed by APScheduler
CREATE TABLE IF NOT EXISTS reddit.feeds (
  id            SERIAL PRIMARY KEY,
  subreddit     TEXT NOT NULL,
  query         TEXT,                     -- NULL means browse listings, not search
  sort          TEXT DEFAULT 'top',
  time_filter   TEXT DEFAULT 'week',
  limit_per_run INT  DEFAULT 25,
  cron_expr     TEXT NOT NULL,            -- documents intended schedule e.g. "0 2 * * *"
  enabled       BOOLEAN DEFAULT TRUE,
  last_run_at   TIMESTAMPTZ,
  last_run_count INT,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ── Existing table grants (for rows created before DEFAULT PRIVILEGES was set) ──

GRANT SELECT, INSERT, UPDATE ON reddit.subreddits  TO reddit_app;
GRANT SELECT, INSERT, UPDATE ON reddit.posts        TO reddit_app;
GRANT SELECT, INSERT, UPDATE ON reddit.comments     TO reddit_app;
GRANT SELECT, INSERT, UPDATE ON reddit.query_cache  TO reddit_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON reddit.feeds TO reddit_app;
GRANT USAGE, SELECT ON SEQUENCE reddit.feeds_id_seq TO reddit_app;
