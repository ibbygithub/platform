# Database Rules — dbnode-01 Access, Ownership, and Agent Constraints

## Core Principle

dbnode-01 is a dedicated database tier. It runs PostgreSQL 17 exclusively.
No Docker. No applications. No ad-hoc schema changes without a documented task plan.
Every database has an owner and a purpose. Never assume a database is available for
general use without checking this file first.

---

## Node Identity

| Property | Value |
|:---|:---|
| **Hostname** | `dbnode-01` |
| **IP Address** | `192.168.71.221` |
| **OS** | Debian Linux |
| **PostgreSQL Version** | 17.7 (Debian 17.7-3.pgdg12+1) |
| **Persona Required** | `dba-agent` only |
| **SSH Key** | `~/.ssh/dba-agent_ed25519` |

---

## Connection Method — Critical

Peer authentication is enabled on the Unix socket. Direct `psql -U postgres`
will fail with a peer authentication error.

**Correct connection method from dbnode-01 shell:**
```bash
sudo -u postgres psql                        # superuser access
sudo -u postgres psql -d <database_name>     # connect to specific database
```

**Correct connection method from laptop (via SSH):**
```bash
ssh -i ~/.ssh/dba-agent_ed25519 dba-agent@192.168.71.221
# Then on the node:
sudo -u postgres psql -d <database_name>
```

**Never attempt:**
```bash
psql -U postgres                    # fails — peer auth on socket
psql -U postgres -h localhost       # use 127.0.0.1 if TCP required
```

If TCP connection is required, use `-h 127.0.0.1` not `-h localhost`.

---

## Database Inventory — Canonical Reference

Six production databases exist. Each has a strict purpose.
**Do not use a database for a purpose other than what is documented here.**

| Database | Owner | Purpose | Status |
|:---|:---|:---|:---|
| `platform_v1` | `dba-agent` | **Active platform services** — scraper, places | ✅ Active |
| `shogun_v1` | `postgres` | **Project Shogun** — trips, surveys, embeddings | ✅ Active |
| `mltrader` | `mltrader_user` | ML trading research and signals | ✅ Active |
| `n8n` | `n8n_user` | n8n automation workflow state | ✅ Active |
| `automation_sandbox_test` | `postgres` | Testing and sandbox only | 🧪 Sandbox |
| `postgres` | `postgres` | PostgreSQL system database | 🚫 Never use |

**Hard Rules:**
- `postgres` database — never connect to this for application work
- `automation_sandbox_test` — safe for destructive testing only, never production data
- Never create tables in a database you do not own without explicit instruction
- Never migrate data between databases without a documented task plan

---

## Database Selection Guide for Agents

Before writing any SQL or schema change, answer this question:
**What service or project does this task belong to?**

| If the task involves... | Use this database |
|:---|:---|
| Scraper service, crawl results, web data | `platform_v1` → `scraper` schema |
| Google Places data for platform services | `platform_v1` → `places` schema |
| Project Shogun features, trips, users | `shogun_v1` → `public` or `places` schema |
| Google Places data for Shogun | `shogun_v1` → `places` schema |
| ML trading models or signals | `mltrader` → `mltrader` schema |
| n8n workflow state | `n8n` → `n8n` schema |
| Experimental or throwaway work | `automation_sandbox_test` |

**If uncertain — stop and ask. Do not guess.**

---

## Installed Extensions

| Extension | Version | Databases | Purpose |
|:---|:---|:---|:---|
| `vector` (pgvector) | 0.8.1 | platform_v1, shogun_v1, mltrader | Vector embeddings and similarity search |
| `pg_stat_statements` | 1.11 | all application databases | Query performance monitoring |
| `pgcrypto` | 1.3 | shogun_v1 only | PII column protection and authentication hashing |
| `plpgsql` | 1.0 | all databases | PL/pgSQL procedural language (PostgreSQL built-in) |

**pg_stat_statements (1.11)** is installed in all application databases for query monitoring.
It is also present in the `postgres` system database for cluster-wide monitoring via
Grafana/pg_monitor. It is NOT a shared global extension — it must be installed per database.

**pgcrypto (1.3)** is installed in `shogun_v1` only. Intended for PII column protection and
authentication hashing. No columns are currently encrypted. Required in any future database
that will handle PII data.

**Platform standard: pgvector minimum version 0.8.1.** All application databases must meet
this minimum. Exceptions must be documented.

pgvector is available for embedding storage. Use it via the `vector` column type.

### New Database Provisioning Checklist

When provisioning a new application database, install extensions in this order:

- **pg_stat_statements**: required at creation for all databases
- **pgvector**: required at creation if the database will store embeddings or vector
  similarity data. Minimum version 0.8.1.
- **pgcrypto**: required at creation for any database that will handle PII, credentials,
  or encrypted data fields.

---

## User Accounts and Roles

| Role | Superuser | Can Login | Member Of | Purpose |
|:---|:---|:---|:---|:---|
| `postgres` | ✅ Yes | ✅ Yes | — | System superuser — infrastructure only |
| `dba-agent` | ❌ No | ✅ Yes | `pg_monitor`, `scraper_app` | Agent DBA persona — platform ops. **Cluster privileges: CREATEROLE, CREATEDB (explicit grants).** Use only for documented provisioning tasks with an approved task plan. Never invoke speculatively. |
| `scraper_app` | ❌ No | ✅ Yes | — | Scraper service application user |
| `places_app` | ❌ No | ✅ Yes | — | Google Places service application user |
| `mcp_shogun` | ❌ No | ✅ Yes | `mcp_group` | MCP server access to Shogun |
| `mcp_group` | ❌ No | ❌ No | — | MCP role group (no direct login) |
| `mltrader_user` | ❌ No | ✅ Yes | — | ML trader application user |
| `n8n_user` | ❌ No | ✅ Yes | — | n8n application user |

**Hard Rules:**
- Application services connect as their designated app user, never as `postgres`
- `postgres` superuser is for infrastructure tasks only — schema creation, user management
- `dba-agent` is the agent persona for all DBA tasks on this node
- Never create a new user account without documenting it in this file

---

## Schema Change Policy

All schema changes (CREATE TABLE, ALTER TABLE, DROP TABLE, CREATE INDEX) require:

1. A documented task plan approved via Stage 2 Execution Plan
2. The target database and schema explicitly named in the plan
3. A rollback strategy stated before execution
4. An evidence record written to `outputs/validation/` after completion

Schema changes are destructive by nature — they follow the same confirmation
rules as all destructive actions per `02-safety.md`.

---

## Hard Block Triggers

| Trigger | Violation Type |
|:---|:---|
| Connecting to `postgres` system database for application work | `CROSS_DB_VIOLATION` |
| Creating tables in wrong database | `CROSS_DB_VIOLATION` |
| Using `postgres` superuser for application queries | `CREDENTIAL_ESCALATION` |
| Schema change without approved task plan | `UNAUTHORIZED_DDL` |
| Connecting via wrong SSH key or persona | `CREDENTIAL_ESCALATION` |
| CREATE DATABASE or DROP DATABASE without an approved task plan | `UNAUTHORIZED_PROVISION` |
| CREATE ROLE, DROP ROLE, or ALTER ROLE without an approved task plan | `UNAUTHORIZED_PROVISION` |

**UNAUTHORIZED_PROVISION — expanded rules:**
- Persona scope: `dba-agent` only (the only persona with CREATEROLE and CREATEDB)
- Required before proceeding: human confirmation with task plan reference or explicit
  session approval — silence is not consent
- Log format: `[HARD BLOCK: UNAUTHORIZED_PROVISION] attempted: <command>`
- Evidence file: `outputs/validation/YYYY-MM-DD_HARDBLOCK_DB_UNAUTHORIZED_PROVISION.md`

Evidence file naming: `outputs/validation/YYYY-MM-DD_HARDBLOCK_DB_<type>.md`

---

## Reference Files

- Full database schemas: `.claude/databases/`
  - `platform_v1.md` — scraper and places schemas
  - `shogun_v1.md` — project Shogun schemas
  - `mltrader.md` — trading database
  - `n8n.md` — automation database
  - `automation_sandbox_test.md` — sandbox database
