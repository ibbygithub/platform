-- =============================================================================
-- Scraper schema — Firecrawl result persistence
-- Database: platform_v1  |  Host: dbnode-01
--
-- Run once by a superuser or a role with CREATE SCHEMA privilege:
--   psql -h dbnode-01 -U postgres -d platform_v1 -f schema.sql
-- =============================================================================

-- Create dedicated schema
CREATE SCHEMA IF NOT EXISTS scraper;

-- ---------------------------------------------------------------------------
-- scraper.scrape_results
-- One row per single-URL scrape (POST /v1/scrape)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scraper.scrape_results (
    id          BIGSERIAL    PRIMARY KEY,
    url         TEXT         NOT NULL,
    title       TEXT,
    markdown    TEXT,
    html        TEXT,
    metadata    JSONB,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE scraper.scrape_results IS
    'Results from single-URL Firecrawl scrape operations.';

-- ---------------------------------------------------------------------------
-- scraper.map_results
-- One row per site-map discovery run (POST /v1/map)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scraper.map_results (
    id          BIGSERIAL    PRIMARY KEY,
    root_url    TEXT         NOT NULL,
    url_count   INTEGER      NOT NULL DEFAULT 0,
    urls        JSONB        NOT NULL DEFAULT '[]',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE scraper.map_results IS
    'URL lists discovered by Firecrawl site-map operations.';

-- ---------------------------------------------------------------------------
-- scraper.crawl_results
-- One row per page within a multi-page crawl job (POST /v1/crawl)
-- All rows from a single crawl share the same session_id.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scraper.crawl_results (
    id          BIGSERIAL    PRIMARY KEY,
    session_id  UUID         NOT NULL,
    url         TEXT         NOT NULL,
    status      TEXT,
    markdown    TEXT,
    metadata    JSONB,
    content_len INTEGER      GENERATED ALWAYS AS (length(markdown)) STORED,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS crawl_results_session_idx
    ON scraper.crawl_results (session_id);

COMMENT ON TABLE scraper.crawl_results IS
    'Per-page results from Firecrawl multi-page crawl jobs. '
    'All pages within one crawl share a session_id.';

-- ---------------------------------------------------------------------------
-- scraper.extract_results
-- One row per LLM extraction run (POST /v1/extract)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scraper.extract_results (
    id          BIGSERIAL    PRIMARY KEY,
    url         TEXT         NOT NULL,
    schema_def  JSONB,
    extracted   JSONB,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE scraper.extract_results IS
    'Structured data extracted by Firecrawl LLM extraction operations.';

-- ---------------------------------------------------------------------------
-- Grant access to the scraper application user
-- Replace scraper_app with the actual role name if different.
-- ---------------------------------------------------------------------------
-- GRANT USAGE ON SCHEMA scraper TO scraper_app;
-- GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA scraper TO scraper_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA scraper TO scraper_app;
