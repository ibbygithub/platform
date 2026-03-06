# Database Reference — n8n

## Identity

| Property | Value |
|:---|:---|
| **Database** | `n8n` |
| **Owner** | `n8n_user` |
| **Primary User** | `n8n_user` |
| **Purpose** | n8n automation workflow state and execution history |
| **Size** | 7.8 MB |

## Connection

```bash
sudo -u postgres psql -d n8n
# Application connects automatically — do not modify connection config
```

## Schemas

### `n8n` schema
Owner: `n8n_user`
Purpose: n8n internal state — workflows, credentials, execution history.
Managed entirely by the n8n application. Do not modify manually.

| Table | Status |
|:---|:---|
| *(managed by n8n application)* | Do not query or modify directly |

## Critical Agent Rule

This database is **fully managed by the n8n application**.
Never write to, alter, or drop anything in this database manually.
If n8n workflow state needs to be inspected, use the n8n web interface.

## Anti-Patterns
- ❌ Do not query n8n tables directly for application data
- ❌ Do not create tables in this database
- ❌ Do not modify n8n schema — application manages its own migrations
