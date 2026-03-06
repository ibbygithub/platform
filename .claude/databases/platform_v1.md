# Database Reference — platform_v1

## Identity

| Property | Value |
|:---|:---|
| **Database** | `platform_v1` |
| **Owner** | `dba-agent` |
| **Primary User** | `scraper_app`, `places_app` |
| **Purpose** | Active platform services — scraper results, Google Places cache |
| **Size** | 8.6 MB |
| **Extensions** | pgvector (vector), pg_stat_statements |

## Connection

```bash
sudo -u postgres psql -d platform_v1
# or as app user:
psql -h 127.0.0.1 -U scraper_app -d platform_v1
psql -h 127.0.0.1 -U places_app -d platform_v1
```

---

## Schemas

### `scraper` schema
Owner: `dba-agent`
Purpose: Stores all results from the Firecrawl/scraper-api service on svcnode-01.
App user: `scraper_app`

| Table | Owner | Size | Rows | Purpose |
|:---|:---|:---|:---|:---|
| `crawl_results` | `dba-agent` | 384 kB | 9 | Full crawl job results |
| `extract_results` | `dba-agent` | 104 kB | 1 | LLM extraction results |
| `map_results` | `dba-agent` | 32 kB | 2 | URL map/discovery results |
| `scrape_results` | `dba-agent` | 136 kB | 2 | Single page scrape results |

**Agent note:** This is the correct schema for all scraper-api persistence tasks.
Do not use `shogun_v1.public` for scraper data — that is a separate project database.

### `places` schema
Owner: `dba-agent`
Purpose: Google Places data cache for platform services.
App user: `places_app`

| Table | Owner | Size | Rows | Purpose |
|:---|:---|:---|:---|:---|
| `google_place_snapshots` | `dba-agent` | 32 kB | 0 | Point-in-time place snapshots |
| `google_places` | `dba-agent` | 40 kB | 0 | Cached place records |

**Agent note:** These tables are empty — data collection not yet started.
The equivalent tables in `shogun_v1.places` have live data (20 places, 60 snapshots).

### `public` schema
Owner: `pg_database_owner`
Purpose: General purpose — currently empty, no application tables.
Do not create application tables here without explicit instruction.

---

## Consumption Pattern

### Scraper service writing results
```python
# Connection string for scraper-api on svcnode-01
DATABASE_URL = "postgresql://scraper_app:<password>@192.168.71.221:5432/platform_v1"

# Schema-qualified table references
INSERT INTO scraper.crawl_results ...
INSERT INTO scraper.scrape_results ...
INSERT INTO scraper.map_results ...
INSERT INTO scraper.extract_results ...
```

### Querying scraper results
```sql
-- Recent crawl results
SELECT * FROM scraper.crawl_results ORDER BY created_at DESC LIMIT 10;

-- Scrape results with content
SELECT url, status_code, content_length FROM scraper.scrape_results;
```

---

## Anti-Patterns — Do Not Do These

- ❌ Do not write scraper results to `shogun_v1` — wrong database
- ❌ Do not use `postgres` superuser for application queries
- ❌ Do not create tables in `public` schema without instruction
- ❌ Do not drop or truncate tables without approved task plan
