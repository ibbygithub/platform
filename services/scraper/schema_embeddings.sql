-- =============================================================================
-- schema_embeddings.sql — Phase 2: upgrade JSONB embeddings to pgvector VECTOR
-- Database: platform_v1  |  Host: dbnode-01
--
-- Prerequisites:
--   1. pgvector extension installed (requires Postgres superuser):
--        sudo -u postgres psql -d platform_v1 -c "CREATE EXTENSION IF NOT EXISTS vector;"
--   2. schema.sql has already been applied (scraper.* tables exist with embedding_json JSONB)
--   3. The scraper-api has been running and has populated embedding_json in the tables
--
-- Run as dba-agent (or any role with ALTER TABLE privilege on scraper.*):
--   psql -U dba-agent -d platform_v1 -f schema_embeddings.sql
-- =============================================================================

BEGIN;

-- ── Verify pgvector is installed ─────────────────────────────────────────────
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
    RAISE EXCEPTION 'pgvector extension is not installed. Run as superuser: CREATE EXTENSION vector;';
  END IF;
  RAISE NOTICE 'pgvector % is installed.', (SELECT extversion FROM pg_extension WHERE extname = 'vector');
END $$;

-- ── Add VECTOR columns ────────────────────────────────────────────────────────
-- text-embedding-3-small produces 1536-dimensional vectors
ALTER TABLE scraper.scrape_results  ADD COLUMN IF NOT EXISTS embedding vector(1536);
ALTER TABLE scraper.crawl_results   ADD COLUMN IF NOT EXISTS embedding vector(1536);
ALTER TABLE scraper.extract_results ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- ── Backfill from embedding_json where data already exists ───────────────────
-- pgvector accepts a string like '[0.1, 0.2, ...]' which matches JSONB array text
UPDATE scraper.scrape_results
SET    embedding = embedding_json::text::vector
WHERE  embedding_json IS NOT NULL AND embedding IS NULL;

UPDATE scraper.crawl_results
SET    embedding = embedding_json::text::vector
WHERE  embedding_json IS NOT NULL AND embedding IS NULL;

UPDATE scraper.extract_results
SET    embedding = embedding_json::text::vector
WHERE  embedding_json IS NOT NULL AND embedding IS NULL;

-- ── HNSW indexes for fast cosine similarity search ───────────────────────────
-- HNSW is preferred over IVFFlat for small-to-medium datasets (no training needed)
CREATE INDEX IF NOT EXISTS scrape_results_embedding_hnsw
    ON scraper.scrape_results
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS crawl_results_embedding_hnsw
    ON scraper.crawl_results
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS extract_results_embedding_hnsw
    ON scraper.extract_results
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ── Grant SELECT on new columns to scraper_app ───────────────────────────────
GRANT SELECT, INSERT, UPDATE ON scraper.scrape_results  TO scraper_app;
GRANT SELECT, INSERT, UPDATE ON scraper.crawl_results   TO scraper_app;
GRANT SELECT, INSERT, UPDATE ON scraper.extract_results TO scraper_app;

-- ── Verification ─────────────────────────────────────────────────────────────
SELECT
    t.table_name,
    c.column_name,
    c.data_type,
    c.udt_name
FROM information_schema.tables   t
JOIN information_schema.columns  c ON c.table_schema = t.table_schema
                                  AND c.table_name   = t.table_name
WHERE t.table_schema = 'scraper'
  AND c.column_name IN ('embedding', 'embedding_json')
ORDER BY t.table_name, c.column_name;

SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'scraper'
  AND indexname LIKE '%embedding%';

COMMIT;
