# Database Reference — automation_sandbox_test

## Identity

| Property | Value |
|:---|:---|
| **Database** | `automation_sandbox_test` |
| **Owner** | `postgres` |
| **Primary User** | `dba-agent`, `postgres` |
| **Purpose** | Safe sandbox for testing, experimentation, destructive operations |
| **Size** | 7.4 MB |

## Connection

```bash
sudo -u postgres psql -d automation_sandbox_test
```

## Extensions

| Extension | Version | Notes |
|:---|:---|:---|
| `pg_stat_statements` | 1.11 | Installed 2026-03-06 |
| `vector` (pgvector) | not installed by default | Install on demand: `CREATE EXTENSION vector;` (safe in sandbox) |
| `pgcrypto` | not installed by default | Install on demand: `CREATE EXTENSION pgcrypto;` (safe in sandbox) |

## Schemas

### `public` schema
Owner: `pg_database_owner`
Currently empty — no tables deployed.

## Purpose and Rules

This is the **only database where destructive operations are permitted without
a full task plan approval**. Use it freely for:

- Testing new schema designs before applying to production databases
- Validating SQL queries before running against live data
- Experimenting with pgvector, new extensions, or new patterns
- Throwaway table creation during development

**It is safe to drop, truncate, and destroy anything in this database.**
Never put data here that you need to keep.

## Anti-Patterns
- ❌ Do not use for production data storage
- ❌ Do not reference this database from application service configs
- ❌ Do not assume data here persists — treat it as ephemeral
