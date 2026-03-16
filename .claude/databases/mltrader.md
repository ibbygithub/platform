# Database Reference — mltrader

## Identity

| Property | Value |
|:---|:---|
| **Database** | `mltrader` |
| **Owner** | `mltrader_user` |
| **Primary User** | `mltrader_user` |
| **Purpose** | ML trading research — models, signals, market data |
| **Size** | 7.6 MB |

## Connection

```bash
sudo -u postgres psql -d mltrader
# or as app user:
psql -h 127.0.0.1 -U mltrader_user -d mltrader
```

## Extensions

| Extension | Version | Notes |
|:---|:---|:---|
| `vector` (pgvector) | 0.8.1 | Upgraded from 0.8.0 on 2026-03-06 |
| `pg_stat_statements` | 1.11 | Installed 2026-03-06 |
| `pgcrypto` | not installed | Not applicable to current use case |

## Schemas

### `mltrader` schema
Owner: `mltrader_user`
Purpose: All trading research tables. Currently empty — schema exists, no tables yet deployed.

| Table | Status |
|:---|:---|
| *(none)* | Schema created, tables not yet deployed |

**Agent note:** This database is owned and operated by the mltrader project.
Do not create tables here without explicit instruction from a trading-related task.
Schema is reserved for ML model outputs, signal history, and market data storage.

## Anti-Patterns
- ❌ Do not use for platform or Shogun data
- ❌ Do not create tables without an approved trading project task plan
