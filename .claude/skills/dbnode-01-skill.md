# Skill — dbnode-01 Database Operations

## When to Use This Skill

Load this skill whenever a task involves:
- Reading from or writing to any database on dbnode-01
- Creating or modifying schemas, tables, or indexes
- Debugging database connection issues
- Running queries against platform, Shogun, trading, or automation data
- Any mention of PostgreSQL, pgvector, or database persistence

## Quick Reference — Database Selection

| Task context | Database | Schema | App user |
|:---|:---|:---|:---|
| Scraper results / web crawl data | `platform_v1` | `scraper` | `scraper_app` |
| Google Places (platform services) | `platform_v1` | `places` | `places_app` |
| Project Shogun features | `shogun_v1` | `public` | `mcp_shogun` |
| Google Places (Shogun project) | `shogun_v1` | `places` | `places_app` |
| ML trading research | `mltrader` | `mltrader` | `mltrader_user` |
| n8n workflows | `n8n` | `n8n` | `n8n_user` (app-managed) |
| Testing / throwaway | `automation_sandbox_test` | `public` | `dba-agent` |

**When uncertain — stop and ask. Never guess the target database.**

## Connection — Always Use This Pattern

```bash
# Step 1: SSH to dbnode-01
ssh -i ~/.ssh/dba-agent_ed25519 dba-agent@192.168.71.221

# Step 2: Connect to target database
sudo -u postgres psql -d <database_name>

# Step 3: Verify you are in the right database
SELECT current_database(), current_user;
```

**Never use:** `psql -U postgres` (peer auth will fail on socket)

## Critical Facts — Memorize These

1. **platform_v1 ≠ shogun_v1** — they are separate databases with separate purposes
   - Scraper data → `platform_v1.scraper`
   - Shogun app data → `shogun_v1.public`
   - Both have a `places` schema but they serve different projects

2. **pgvector is installed** — use `vector` column type for embeddings
   - Extension: `vector` v0.8.1 in `public` schema
   - Distance operator: `<->` for similarity search

3. **Schema-qualify all table references** — always use `schema.table` format
   - ✅ `SELECT * FROM scraper.crawl_results`
   - ❌ `SELECT * FROM crawl_results` (ambiguous)

4. **postgres superuser = infrastructure only** — application queries use app users

5. **n8n database = hands off** — fully managed by n8n application

## Pre-Task Checklist

Before writing any SQL or schema change:
- [ ] Confirmed target database from the selection table above
- [ ] Confirmed target schema within that database
- [ ] Confirmed app user for connection
- [ ] Checked `05-database.md` for any hard block triggers
- [ ] If schema change: task plan approved, rollback strategy documented
- [ ] If operating as dba-agent: this persona holds CREATEROLE and CREATEDB cluster
      privileges. Any task involving CREATE DATABASE, DROP DATABASE, CREATE ROLE,
      DROP ROLE, or ALTER ROLE requires an approved task plan before execution.
      Unauthorized use triggers UNAUTHORIZED_PROVISION hard block — stop and confirm.

## Useful Diagnostic Queries

```sql
-- Confirm current database and user
SELECT current_database(), current_user, version();

-- List all schemas in current database
SELECT schema_name, schema_owner FROM information_schema.schemata
WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
ORDER BY schema_name;

-- List all tables with sizes and row counts
SELECT schemaname, tablename, tableowner,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY schemaname, tablename;

-- Check active connections
SELECT datname, usename, application_name, state, query_start
FROM pg_stat_activity
WHERE datname IS NOT NULL
ORDER BY datname, query_start;

-- Check pgvector extension
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
```

## Reference Files

- Rules and hard blocks: `.claude/rules/05-database.md`
- platform_v1 schema detail: `.claude/databases/platform_v1.md`
- shogun_v1 schema detail: `.claude/databases/shogun_v1.md`
- mltrader schema detail: `.claude/databases/mltrader.md`
- n8n schema detail: `.claude/databases/n8n.md`
- sandbox detail: `.claude/databases/automation_sandbox_test.md`
