# dbnode-01 Documentation Audit Report

**Date:** 2026-03-06
**Requested filename:** 2026-03-05_dbnode01-docs-audit-report.md
**Auditor:** dba-agent persona via Claude Code
**Method:** Static analysis of 7 documentation files + live verification queries on dbnode-01
**Node:** dbnode-01 (192.168.71.221) — PostgreSQL 17.7

---

## Executive Summary

The dbnode-01 documentation suite is structurally sound and provides adequate baseline
coverage for the most common agent tasks. The connection method guidance is accurate and
consistent across all files. Database routing logic is unambiguous for the majority of cases.

However, the audit identified **15 findings** across the five audit areas, including
**2 Critical** and **5 High** severity items that require immediate remediation.

The most significant gap is a **Critical undocumented privilege**: `dba-agent` holds
`CREATEROLE` and `CREATEDB` at the cluster level — capabilities that are nowhere documented
and for which no hard block guard exists. A second Critical finding is a systematic
**extension inventory mismatch**: `pg_stat_statements` is listed as a global extension
in both `05-database.md` and two database reference files, but live verification shows it
is only installed in the `postgres` system database and `n8n`. Three databases where
documentation implies it is present (`platform_v1`, `shogun_v1`) do not have it.

**Overall documentation readiness: CONDITIONAL — not recommended for unsupervised agent use
until Critical and High findings are resolved.**

---

## Files Audited

| File | Lines | Purpose |
|:---|:---|:---|
| `.claude/rules/05-database.md` | 163 | Master rules — node identity, connection, inventory, hard blocks |
| `.claude/databases/platform_v1.md` | 91 | platform_v1 schema reference |
| `.claude/databases/shogun_v1.md` | 110 | shogun_v1 schema reference |
| `.claude/databases/mltrader.md` | 38 | mltrader schema reference |
| `.claude/databases/n8n.md` | 41 | n8n schema reference |
| `.claude/databases/automation_sandbox_test.md` | 42 | sandbox schema reference |
| `.claude/skills/dbnode-01-skill.md` | 105 | Agent quick reference and decision logic |

---

## Area 1 — Authentication and Connection Methods

**Assessment: MOSTLY ACCURATE — one omission**

The core connection guidance is correct and consistent across all files:
- `sudo -u postgres psql -d <db>` for superuser/admin access — verified accurate
- `psql -h 127.0.0.1 -U <app_user> -d <db>` for application user TCP connections — verified accurate
- The peer auth warning is accurate: direct `psql -U postgres` fails on the Unix socket
- SSH key and persona mapping is consistent across all files

### Finding A1-1 — LOW

**Title:** `n8n.md` omits TCP connection string for n8n_user

**File:** `.claude/databases/n8n.md`, line 16

**Observation:** `n8n.md` only documents the superuser connection pattern:
```bash
sudo -u postgres psql -d n8n
# Application connects automatically — do not modify connection config
```
All other database reference files include both the superuser and app-user TCP patterns.
While `n8n` is app-managed and the agent should not connect as `n8n_user` for application
work, an agent that needs to inspect the database state cannot derive the TCP pattern from
this file.

**Recommended fix:** Add informational TCP pattern for reference, clearly marked read-only
inspection only:
```bash
# For inspection only — do not use for application queries:
psql -h 127.0.0.1 -U n8n_user -d n8n
```

---

## Area 2 — Role and Permission Gaps

**Assessment: CRITICAL GAPS — live state materially differs from documentation**

### Finding A2-1 — CRITICAL

**Title:** `dba-agent` holds undocumented CREATEROLE and CREATEDB cluster privileges

**File:** `.claude/rules/05-database.md`, lines 108–117 (User Accounts table)

**Live verification:**
```sql
SELECT rolname, rolsuper, rolcanlogin, rolcreaterole, rolcreatedb
FROM pg_roles WHERE rolname = 'dba-agent';
-- Result: rolcreaterole=t, rolcreatedb=t
```

**Observation:** The documentation User Accounts table states `dba-agent` is not a
superuser, which is correct. However, it entirely omits that `dba-agent` holds
`CREATEROLE` and `CREATEDB` — the ability to create new databases and new roles on the
entire PostgreSQL cluster. These are not default non-superuser privileges; they were
explicitly granted. This is a major security-relevant capability that is:
- Not documented anywhere in the 7-file suite
- Not guarded by any hard block trigger
- Not included in the skill file's role capability description

An agent operating as dba-agent could create databases and roles without this being
flagged as an unauthorized action under current documentation.

**Recommended fix:**
1. Add a "Cluster Privileges" column or note to the User Accounts table in `05-database.md`:
   `dba-agent: CREATEROLE, CREATEDB (explicit grants — use only for documented provisioning tasks)`
2. Add a hard block trigger: creating a database or role without an approved task plan
   → `UNAUTHORIZED_PROVISION`
3. Add a note in the skill file Pre-Task Checklist flagging this capability

---

### Finding A2-2 — HIGH

**Title:** `pg_stat_statements` documented as global but only installed in `postgres` and `n8n`

**Files:**
- `.claude/rules/05-database.md`, lines 94–101 (Installed Extensions table)
- `.claude/databases/platform_v1.md`, line 12 (Extensions field)
- `.claude/databases/shogun_v1.md`, line 12 (Extensions field)

**Live verification:**
```
postgres:       pg_stat_statements 1.11  ✅
platform_v1:    NOT installed            ❌ (doc says it is)
shogun_v1:      NOT installed            ❌ (doc says it is)
mltrader:       NOT installed            (not documented — consistent)
n8n:            pg_stat_statements 1.11  (not documented — app-managed)
automation_sandbox_test: NOT installed   (not documented — consistent)
```

**Observation:** `05-database.md` presents `pg_stat_statements` as a globally installed
extension alongside `vector`. The platform_v1 and shogun_v1 reference files echo this.
In reality it is installed only in the `postgres` system database (where it monitors
cluster-wide query stats) and in `n8n` (app-managed install). Any agent or developer
attempting to use `pg_stat_statements` views in `platform_v1` or `shogun_v1` will get
a "relation does not exist" error.

**Recommended fix:**
1. Remove `pg_stat_statements` from the global extensions table in `05-database.md`
2. Add a note: "pg_stat_statements is installed in the `postgres` system database only
   for cluster-wide monitoring via Grafana/pg_monitor. It is not available in application databases."
3. Correct the Extensions fields in `platform_v1.md` and `shogun_v1.md`

---

### Finding A2-3 — HIGH

**Title:** `pgcrypto` installed in `shogun_v1` — completely undocumented

**Files:**
- `.claude/databases/shogun_v1.md`, line 12 (Extensions field lists only "pgvector, pg_stat_statements")
- `.claude/rules/05-database.md`, lines 94–101 (Installed Extensions table)

**Live verification:**
```
shogun_v1: pgcrypto 1.3  ✅ (installed, not documented anywhere)
```

**Observation:** `pgcrypto` is installed in `shogun_v1` but appears in no documentation.
This extension provides cryptographic functions (`crypt()`, `gen_salt()`, `pgp_sym_encrypt()`,
etc.) — its presence implies it is being used or was planned for password hashing or
encryption in the Shogun schema. An agent that needs to use cryptographic functions would
not know this capability exists, while an agent auditing the extensions would not expect
this install.

**Recommended fix:**
1. Add `pgcrypto 1.3` to the Extensions field in `shogun_v1.md`
2. Add a note explaining its purpose (password hashing for `users` table, or similar)
3. Add it to the `05-database.md` Installed Extensions table scoped to `shogun_v1`

---

### Finding A2-4 — HIGH

**Title:** `mcp_group` has full SELECT/INSERT/UPDATE/DELETE on all 17 shogun_v1.public tables — grant scope undocumented

**Files:**
- `.claude/rules/05-database.md`, line 114 (`mcp_shogun` entry says "MCP server access to Shogun")
- `.claude/databases/shogun_v1.md`, line 81 ("mcp_shogun role has read/write access")

**Live verification:**
```sql
-- mcp_group has SELECT, INSERT, UPDATE, DELETE on all 17 tables in shogun_v1.public
-- including: users, trips, trip_events, trip_members, survey_votes, dev_logs, etc.
-- mcp_shogun inherits these via group membership
```

**Observation:** The documentation describes `mcp_shogun` as having "read/write access"
and `mcp_group` as a "role group" — but neither file documents that this means full
CRUD (including DELETE) on **all** 17 tables including `users`. An agent that knows
`mcp_shogun` has "read/write" access might assume SELECT+INSERT+UPDATE only. The actual
DELETE capability on sensitive tables like `users`, `trip_members`, and `survey_votes`
is undocumented and carries significant risk if an agent makes an incorrect inference
about safe operations.

Additionally: `mcp_shogun` does NOT have access to `shogun_v1.places` — this important
scoping restriction is nowhere documented.

**Recommended fix:**
1. In `05-database.md` User Accounts table, expand `mcp_group` description to:
   "Full CRUD (SELECT/INSERT/UPDATE/DELETE) on all shogun_v1.public tables. No access to places schema."
2. In `shogun_v1.md`, replace "read/write access" with explicit grant summary
3. Document the places schema exclusion for mcp_shogun explicitly

---

### Finding A2-5 — MEDIUM

**Title:** `scraper_app` has no DELETE privilege on scraper schema tables — undocumented restriction

**File:** `.claude/databases/platform_v1.md`, lines 29–39 (Schemas → scraper section)

**Live verification:**
```sql
-- scraper_app grants on scraper schema: SELECT, INSERT, UPDATE only
-- No DELETE privilege
```

**Observation:** The scraper schema section documents `scraper_app` as the app user
but does not mention the absence of DELETE. This is an intentional access restriction
(write-only pipeline — results are never deleted by the app user) but an agent
implementing a "cleanup old results" feature would not know to escalate to dba-agent
for DELETE operations, potentially leading to permission errors or incorrect user choice.

**Recommended fix:** Add a note to `platform_v1.md` scraper schema section:
> `scraper_app` has SELECT, INSERT, UPDATE. No DELETE — use dba-agent for any cleanup
> or purge operations requiring DELETE on scraper tables.

---

### Finding A2-6 — MEDIUM

**Title:** `vector` extension version inconsistency — mltrader has 0.8.0, docs say 0.8.1

**Files:**
- `.claude/rules/05-database.md`, line 98 (vector 0.8.1)
- `.claude/skills/dbnode-01-skill.md`, line 49 (vector v0.8.1)

**Live verification:**
```
platform_v1:  vector 0.8.1  ✅
shogun_v1:    vector 0.8.1  ✅
mltrader:     vector 0.8.0  ❌ (docs imply 0.8.1 globally)
n8n:          vector 0.8.0  (undocumented — app-managed)
```

**Observation:** The documentation describes vector 0.8.1 as the installed version with
no per-database qualification. `mltrader` has the older 0.8.0. While the functional
difference may be minor, the documentation should be accurate and per-database scoped.

**Recommended fix:**
1. Update `05-database.md` Installed Extensions table to note the per-database versions
2. Add `Extensions: vector 0.8.0` to `mltrader.md`

---

### Finding A2-7 — LOW

**Title:** `neighborhood_anchors` table in shogun_v1.places is owned by `places_app`, not `postgres`

**File:** `.claude/databases/shogun_v1.md`, line 59 (table shows no explicit owner column for places schema)

**Live verification:**
```sql
-- shogun_v1.places:
-- google_places owner: postgres
-- google_place_snapshots owner: postgres
-- neighborhood_anchors owner: places_app  ← inconsistent
```

**Observation:** The `shogun_v1.md` places schema table does not include an Owner column
(unlike the public schema table). The live state shows `neighborhood_anchors` is owned by
`places_app`, not `postgres` like the other two places tables. This ownership inconsistency
is invisible in documentation and could matter for permission management tasks.

**Recommended fix:** Add an Owner column to the places schema table in `shogun_v1.md`
with the accurate per-table ownership.

---

## Area 3 — Agent Decision Logic

**Assessment: MOSTLY UNAMBIGUOUS — one routing risk, one missing distinction**

### Finding A3-1 — HIGH

**Title:** "Google Places" routing requires consumer context that is not captured in task framing

**Files:**
- `.claude/rules/05-database.md`, lines 82–85 (Database Selection Guide)
- `.claude/skills/dbnode-01-skill.md`, lines 17–19 (Quick Reference table)

**Observation:** Both the rules file and the skill file correctly document the split:
- Google Places for platform services → `platform_v1.places`
- Google Places for Shogun → `shogun_v1.places`

However, the routing decision depends on the consuming system (which project is requesting
the data), not on any attribute of the Places data itself. An agent receiving a task like
"store the Google Places results from this crawl" has no way to determine the correct
database without knowing the task's project context. The skill file notes "When uncertain —
stop and ask" which is correct, but the decision table's column header is "Task context"
which does not make the consumer-dependency explicit.

The risk is compounded by the fact that `platform_v1.places` is empty while `shogun_v1.places`
has 20 live records — an agent that misroutes a Places write to the wrong database creates
a silent data split.

**Recommended fix:**
1. Reframe the routing rows in both files to make the consumer the primary key:
   > "Task is part of a platform-tier service (scraper-api, places-gateway) → `platform_v1`"
   > "Task is part of Project Shogun (trips, lodging, activities) → `shogun_v1`"
2. Add an explicit warning: "If you cannot identify the consuming project, stop and ask.
   Do not infer from data content alone."

---

### Finding A3-2 — MEDIUM

**Title:** Skill file does not distinguish MCP server tasks from ETL/ingestion tasks for shogun_v1

**File:** `.claude/skills/dbnode-01-skill.md`, lines 18–19

**Observation:** The skill's Quick Reference table lists `mcp_shogun` as the app user
for all "Project Shogun features" tasks. However, `mcp_shogun` is specifically the MCP
server's database identity — ETL scripts, ingestion pipelines, or other backend processes
running on brainnode-01 that write to Shogun would also use `mcp_shogun` by default
(since it's the only documented non-superuser for shogun_v1.public). This collapses
two distinct access patterns into one row. If a future ETL task needs separate permissions
(e.g., bulk DELETE for purge operations, or `shogun_v1.places` write access), the skill
table provides no guidance on how to handle the distinction.

**Recommended fix:** Split the Shogun row or add a note:
> "Project Shogun features (MCP server) → mcp_shogun"
> "Project Shogun ETL/ingestion (brainnode-01 scripts) → mcp_shogun (same user, confirm scope)"
Add a note that mcp_shogun/mcp_group does NOT have access to shogun_v1.places.

---

## Area 4 — Hard Block Trigger Completeness

**Assessment: INCOMPLETE — two critical failure modes unguarded**

### Finding A4-1 — HIGH

**Title:** No hard block for database or role creation without authorization

**File:** `.claude/rules/05-database.md`, lines 141–151 (Hard Block Triggers table)

**Observation:** `dba-agent` has CREATEROLE and CREATEDB (see A2-1). The current hard
block table covers schema-level DDL (`UNAUTHORIZED_DDL`) but has no trigger for:
- `CREATE DATABASE`
- `DROP DATABASE`
- `CREATE ROLE` / `DROP ROLE`
- `ALTER ROLE` (privilege escalation)

An agent executing these cluster-level operations without authorization would not trigger
any documented hard block under current rules.

**Recommended fix:** Add triggers to the Hard Block table:
| Trigger | Violation Type |
|:---|:---|
| Creating or dropping a database without approved task plan | `UNAUTHORIZED_PROVISION` |
| Creating, dropping, or altering a role without approved task plan | `UNAUTHORIZED_PROVISION` |

---

### Finding A4-2 — HIGH

**Title:** No hard block for writing to the n8n database

**Files:**
- `.claude/databases/n8n.md`, lines 33–35 ("Never write to, alter, or drop anything in this database manually")
- `.claude/rules/05-database.md`, lines 141–151 (Hard Block Triggers — no n8n entry)

**Observation:** `n8n.md` has the strongest prohibition language of any database doc:
"Never write to, alter, or drop anything in this database manually." However, this
prohibition is isolated to the n8n reference file and does not appear as a hard block
trigger in `05-database.md`. An agent that hasn't loaded `n8n.md` (or is relying only
on `05-database.md` and the skill file) would have no hard block warning before
issuing DML against n8n tables.

**Recommended fix:** Add to the Hard Block Triggers table in `05-database.md`:
| Trigger | Violation Type |
|:---|:---|
| Any DML or DDL against the `n8n` database | `MANAGED_DB_VIOLATION` |

---

### Finding A4-3 — MEDIUM

**Title:** `UNAUTHORIZED_DDL` trigger scope is too narrow — excludes CREATE SCHEMA, CREATE EXTENSION

**File:** `.claude/rules/05-database.md`, lines 128–137 (Schema Change Policy) and lines 141–151

**Observation:** The Schema Change Policy explicitly lists: "CREATE TABLE, ALTER TABLE,
DROP TABLE, CREATE INDEX." The hard block trigger `UNAUTHORIZED_DDL` refers to "Schema
change without approved task plan." However, the following are not mentioned:
- `CREATE SCHEMA` / `DROP SCHEMA` (schema-level structural changes)
- `CREATE EXTENSION` / `DROP EXTENSION` (cluster capability changes)
- `TRUNCATE` (data-destroying, though not strictly DDL)

An agent interpreting the rules literally could create a new schema or install an extension
without believing it is triggering `UNAUTHORIZED_DDL`.

**Recommended fix:** Expand the Schema Change Policy definition to explicitly include
`CREATE SCHEMA`, `DROP SCHEMA`, `CREATE EXTENSION`, and `DROP EXTENSION`.

---

### Finding A4-4 — LOW

**Title:** `automation_sandbox_test` has no pgvector extension — contradicts stated use case

**File:** `.claude/databases/automation_sandbox_test.md`, lines 29–33

**Observation:** `automation_sandbox_test.md` explicitly states the database is intended for
"Experimenting with pgvector, new extensions, or new patterns." However, live verification
shows `vector` (pgvector) is NOT installed in this database. An agent following this
guidance would fail immediately when attempting to use vector column types or operators.

This is not a hard block issue but is a documentation accuracy problem that could waste
significant agent time debugging an extension-not-found error.

**Recommended fix:** Either install pgvector in `automation_sandbox_test`, or update the
documentation to reflect that extensions must be installed on demand before experimentation
begins: `CREATE EXTENSION vector;` (safe to run in sandbox).

---

## Area 5 — Cross-File Consistency

**Assessment: SEVERAL INCONSISTENCIES — primarily extension inventory errors**

### Finding A5-1 — MEDIUM

**Title:** Extension fields in platform_v1.md and shogun_v1.md are both incorrect

**Files:**
- `.claude/databases/platform_v1.md`, line 12: "Extensions: pgvector (vector), pg_stat_statements"
- `.claude/databases/shogun_v1.md`, line 12: "Extensions: pgvector (vector), pg_stat_statements"

**Live state:**
- `platform_v1`: vector 0.8.1 only (no pg_stat_statements)
- `shogun_v1`: vector 0.8.1 + pgcrypto 1.3 (no pg_stat_statements)

Both files have the same wrong entry. This is a copy-paste propagation of the A2-2 error.
These should each reflect their own actual extension inventory.

**Recommended fix:** Correct each file independently per live verification results.
(This fix is subsumed by A2-2 and A2-3 recommendations — resolve those to fix A5-1.)

---

### Finding A5-2 — MEDIUM

**Title:** `shogun_v1.md` connection section omits `places_app` as a valid direct-connect user

**File:** `.claude/databases/shogun_v1.md`, lines 17–20

**Observation:** The connection section only documents `mcp_shogun`:
```bash
psql -h 127.0.0.1 -U mcp_shogun -d shogun_v1
```
Live verification confirms `places_app` has full CREATE/CONNECT/TEMP privileges on
`shogun_v1` and full DML on `shogun_v1.places`. An agent implementing a places data
pipeline for Shogun would not know the correct connection string from this file alone.
The skill file also omits `places_app` as a connection user for shogun_v1 (the Shogun
row in the Quick Reference only lists `mcp_shogun`).

**Recommended fix:** Add `places_app` connection to the shogun_v1.md connection section,
scoped to the places schema:
```bash
# For places schema operations:
psql -h 127.0.0.1 -U places_app -d shogun_v1
```
Update the skill file Quick Reference to show `places_app` for `shogun_v1.places`.

---

### Finding A5-3 — LOW

**Title:** `mltrader.md` has no Extensions section despite vector 0.8.0 being installed

**File:** `.claude/databases/mltrader.md` (no extensions section present)

**Observation:** All other database reference files include an Extensions field.
`mltrader.md` omits it entirely. The database has `vector 0.8.0` installed — relevant
given the database's stated purpose (ML models, signals) where embeddings are likely.

**Recommended fix:** Add an Extensions field: `vector 0.8.0` (note version is 0.8.0,
not 0.8.1 as deployed elsewhere).

---

### Finding A5-4 — LOW

**Title:** `05-database.md` "six production databases" count is accurate but misleads on system databases

**File:** `.claude/rules/05-database.md`, line 55

**Observation:** The file states "Six production databases exist." The live cluster has
8 databases: the 6 documented ones plus `template0` and `template1` (PostgreSQL system
templates). While template databases are not application databases and the statement is
technically defensible, a new engineer or agent examining the cluster with `\l` would see
8 databases and the count discrepancy could cause confusion during an audit.

**Recommended fix:** Clarify wording: "Six application databases exist. PostgreSQL system
databases (template0, template1, postgres) are not listed here and must never be used for
application work."

---

## Findings Summary

| ID | Severity | Area | Title |
|:---|:---|:---|:---|
| A2-1 | **CRITICAL** | Roles & Permissions | dba-agent has undocumented CREATEROLE+CREATEDB privileges |
| A2-2 | **CRITICAL** | Roles & Permissions | pg_stat_statements documented as global but installed in postgres/n8n only |
| A2-3 | HIGH | Roles & Permissions | pgcrypto installed in shogun_v1 — completely undocumented |
| A2-4 | HIGH | Roles & Permissions | mcp_group full CRUD scope undocumented; places schema exclusion undocumented |
| A3-1 | HIGH | Decision Logic | Google Places routing is consumer-dependent — task framing ambiguity |
| A4-1 | HIGH | Hard Blocks | No hard block for CREATE/DROP DATABASE or CREATE/DROP ROLE |
| A4-2 | HIGH | Hard Blocks | No hard block for writing to the n8n database |
| A2-5 | MEDIUM | Roles & Permissions | scraper_app has no DELETE on scraper tables — undocumented |
| A2-6 | MEDIUM | Roles & Permissions | vector version inconsistency (mltrader has 0.8.0, docs say 0.8.1) |
| A3-2 | MEDIUM | Decision Logic | Skill file collapses MCP and ETL access patterns for shogun_v1 |
| A4-3 | MEDIUM | Hard Blocks | UNAUTHORIZED_DDL excludes CREATE SCHEMA and CREATE EXTENSION |
| A5-1 | MEDIUM | Consistency | Extension fields wrong in platform_v1.md and shogun_v1.md |
| A5-2 | MEDIUM | Consistency | shogun_v1.md omits places_app as a valid connection user |
| A1-1 | LOW | Connection Methods | n8n.md omits TCP connection string |
| A2-7 | LOW | Roles & Permissions | neighborhood_anchors owned by places_app, not postgres — undocumented |
| A4-4 | LOW | Hard Blocks | automation_sandbox_test lacks pgvector extension despite doc saying it supports it |
| A5-3 | LOW | Consistency | mltrader.md has no Extensions section |
| A5-4 | LOW | Consistency | "Six databases" count excludes system databases without explanation |

---

## Overall Documentation Readiness Assessment

**Rating: CONDITIONAL — resolve Critical and High findings before unsupervised agent use**

The documentation provides a solid foundation. Connection methods, persona assignment,
database ownership, and the core routing table are accurate and would correctly guide an
agent through the majority of common tasks. The two-stage approval process and scope
discipline rules provide a structural safety net that compensates for some documentation
gaps.

The Critical and High findings represent genuine risk vectors:
- An agent operating as dba-agent could create databases or roles without hitting any
  documented guard (A2-1, A4-1)
- An agent attempting to use `pg_stat_statements` in `platform_v1` or `shogun_v1` will
  fail with no documentation explaining why (A2-2)
- An agent writing to the n8n database has no formal hard block stopping it (A4-2)
- An agent receiving a generic "store Google Places data" task could silently misroute
  it (A3-1)

**Recommended remediation priority:**
1. A2-1 + A4-1 (dba-agent privilege documentation + hard block) — same root cause, fix together
2. A2-2 + A5-1 (extension inventory correction across all files)
3. A4-2 (n8n write hard block in 05-database.md)
4. A2-3 (pgcrypto documentation in shogun_v1.md and 05-database.md)
5. A2-4 + A5-2 (mcp_group grant scope and shogun_v1 places_app connection)
6. A3-1 (Google Places routing clarification)
7. Remaining Medium and Low items

---

*Report generated: 2026-03-06*
*Live queries executed as: dba-agent@192.168.71.221 → sudo -u postgres psql*
*All findings verified against PostgreSQL 17.7 (Debian 17.7-3.pgdg12+1)*
