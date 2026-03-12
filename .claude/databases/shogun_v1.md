# Database Reference — shogun_v1

## Identity

| Property | Value |
|:---|:---|
| **Database** | `shogun_v1` |
| **Owner** | `postgres` |
| **Primary User** | `mcp_shogun` |
| **Purpose** | Project Shogun — trips, surveys, embeddings, places |
| **Size** | 9.3 MB (largest active database) |
| **Extensions** | vector 0.8.1, pg_stat_statements 1.11, pgcrypto 1.3 — installed for PII/auth column protection; no columns currently encrypted; encryption implementation requires an approved task plan |

## Connection

```bash
sudo -u postgres psql -d shogun_v1
# or as app user (public schema — CRUD via mcp_group):
psql -h 127.0.0.1 -U mcp_shogun -d shogun_v1
# or as app user (places schema operations only):
psql -h 127.0.0.1 -U places_app -d shogun_v1
# Note: places_app has full DML on shogun_v1.places schema only.
#       It does not have access to public schema tables.
```

---

## Schemas

### `public` schema
Owner: `pg_database_owner`
Purpose: Core Project Shogun application tables.

| Table | Owner | Size | Rows | Purpose |
|:---|:---|:---|:---|:---|
| `users` | `postgres` | 80 kB | 1 | User accounts |
| `trips` | `postgres` | 32 kB | 1 | Trip records |
| `trip_events` | `postgres` | 80 kB | 7 | Events within trips |
| `trip_members` | `postgres` | 16 kB | 0 | Trip membership |
| `sources` | `postgres` | 80 kB | 2 | Data source registry |
| `ingestion_runs` | `postgres` | 32 kB | 2 | ETL ingestion tracking |
| `document_embeddings` | `postgres` | 32 kB | 0 | pgvector embeddings |
| `documents` | `postgres` | 40 kB | 0 | Document storage |
| `lodging_details` | `postgres` | 64 kB | 3 | Accommodation records |
| `activities` | `postgres` | 16 kB | 0 | Activity records |
| `locations` | `postgres` | 24 kB | 0 | Location records |
| `expenses` | `postgres` | 24 kB | 0 | Expense tracking |
| `raw_ingestion` | `postgres` | 16 kB | 0 | Raw ingestion staging |
| `surveys` | `postgres` | 24 kB | 0 | Survey definitions |
| `survey_options` | `postgres` | 16 kB | 0 | Survey answer options |
| `survey_votes` | `postgres` | 24 kB | 0 | Survey responses |
| `dev_logs` | `postgres` | 16 kB | 0 | Development logging |

---

## Key Observations for Agents

- `document_embeddings` uses pgvector — queries should use `<->` distance operator
- `ingestion_runs` tracks ETL pipeline executions — check here before re-running ingestion
- `sources` registry — register new data sources here before ingesting
- `lodging_details` has 3 records, `trips` has 1 — this is early-stage data
- `dev_logs` exists for development debugging — structured log output goes here

---

## Consumption Pattern

### MCP server connection
```python
# mcp_shogun role has read/write access
DATABASE_URL = "postgresql://mcp_shogun:<password>@192.168.71.221:5432/shogun_v1"
```

### Vector similarity search
```sql
-- Find similar documents using pgvector
SELECT id, content, embedding <-> '[...]'::vector AS distance
FROM public.document_embeddings
ORDER BY distance
LIMIT 10;
```

### Checking ingestion state
```sql
-- Before running ingestion, check what's already been processed
SELECT source_id, started_at, completed_at, status
FROM public.ingestion_runs
ORDER BY started_at DESC;
```

---

## Anti-Patterns — Do Not Do These

- ❌ Do not write scraper/platform results here — use `platform_v1`
- ❌ Do not write Google Places data here — use `platform_v1.places` (canonical, 2026-03-12)
- ❌ Do not drop any table — all 20 tables are part of the Shogun schema
- ❌ Do not use this database for sandbox testing — use `automation_sandbox_test`
