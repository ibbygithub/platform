# Session Reflection — 2026-03-06
**Type:** Read-only reflection — no files modified
**Session Work:** dbnode-01 docs audit remediation (5 batches) + svcnode-01 git sync
              audit + svcnode-01 discovery audit (4 checks)

---

## 1. SUGGESTED UPDATES

### `.claude/rules/01-infrastructure.md`

**Issue A — dbnode-01 database scope understated (line 12)**
Current:
```
Runs: PostgreSQL `shogun_v1` exclusively
```
This was accurate when the file was first written but is now wrong.
dbnode-01 hosts six application databases (platform_v1, shogun_v1, mltrader,
n8n, automation_sandbox_test) plus the postgres system database.

Proposed replacement:
```
Runs: PostgreSQL 17.7 — six application databases (platform_v1, shogun_v1,
      mltrader, n8n, automation_sandbox_test) plus postgres system database
```

**Issue B — svcnode-01 "Does NOT" claim is incomplete (line 7)**
Current:
```
Does NOT: store persistent data, host application logic, run cron jobs
```
svcnode-01 hosts logstack (Loki + Grafana) which persists log data at
`/opt/logstack/`. This is observability infrastructure, not application data,
but the blanket "does not store persistent data" is misleading.

Proposed addition:
```
Does NOT: store application data, host platform application logic, run cron jobs
Note: /opt/logstack/ stores Grafana Alloy + Loki log retention data.
      This is node-resident observability infrastructure, not platform app data.
```

**Issue C — Firecrawl path exception row missing ownership and network facts (line 79)**
Current row:
```
| Firecrawl | `/opt/firecrawl` | svcnode-01 | Installed via upstream Docker Compose repo before path standard was codified. Root-owned `.env`. Migration risk exceeds benefit. Exception approved 2026-03-05. |
```
The exception exists but does not document two critical operational facts
confirmed during today's discovery audit:
1. All `/opt/firecrawl/` files are owned by `root:root` — devops-agent
   cannot read `.env`, run git commands, or inspect configs via SSH as devops-agent
2. Firecrawl containers run on a `backend` Docker network, NOT `platform_net`

Proposed replacement:
```
| Firecrawl | `/opt/firecrawl` | svcnode-01 | Installed via upstream Docker Compose repo before path standard was codified. Root-owned `.env`. Migration risk exceeds benefit. Exception approved 2026-03-05. Ownership: root:root throughout — devops-agent cannot read .env or run git commands. Network: firecrawl containers join `backend` network only, NOT platform_net. |
```

---

### `.claude/services/_index.md`

**Issue A — Loki and Grafana listings do not note node-resident nature**
Current rows list Loki and Grafana as internal services with IPs and ports,
but give no indication they are deployed node-resident at `/opt/logstack/`
and are NOT managed via the platform git repo.

An agent reading the index might attempt to modify these services via the repo.

Proposed addition to both rows (Notes column or footnote):
```
NODE_ONLY — deployed at /opt/logstack/ on svcnode-01, not tracked in platform git repo
```

**Issue B — Scraper entry does not mention Firecrawl dependency**
Current scraper row describes the service but does not mention that it depends
on Firecrawl running on the same node. An agent working on the scraper
service needs to know that Firecrawl is a sidecar dependency, not a platform
gateway, and that the connection path is via host port 3002 (not platform_net).

Proposed: Add a Notes column entry or companion line to the Scraper row:
```
Depends on Firecrawl at host port 3002 (not platform_net) — see /opt/firecrawl
```

---

### `.claude/CLAUDE.md` (project level)

**Issue A — Session startup Step 3 uses generic language**
Current Step 3:
```
Read `outputs/validation/` and identify the three most recent evidence files.
```
This is correct as a general protocol. No change needed to the procedure.
However, the CLAUDE.md could benefit from a "Known Infrastructure State" section
(see Section 4 below) to give future agents startup context without requiring
full re-discovery.

**Issue B — No reference to settings.json governing agent permissions**
`settings.json` was created this session with granular SSH and git permission
rules. The project CLAUDE.md does not mention it. Future agents should know
this file exists and governs what tool calls are auto-approved vs. require
confirmation.

Proposed addition (after Session Startup Protocol):
```
## Agent Permission Boundaries
SSH, git push, and worktree operations are governed by `.claude/settings.json`.
Review this file at session start if encountering unexpected permission prompts.
```

---

### `~/.claude/CLAUDE.md` (global level)

No substantive gaps identified. The global rules (SSH persona separation,
transport rules, destructive action confirmation, hard block format) remain
accurate and were all exercised correctly during today's session.

The only potential addition would be a note that `settings.json` now exists
at the project level and governs automated approvals — but this is
project-specific and belongs in the project CLAUDE.md, not the global file.

---

## 2. NEW KNOWLEDGE

The following facts were confirmed during today's session. None are currently
captured in any platform documentation.

| Fact | Confirmed By | Documentation Gap |
|:---|:---|:---|
| Firecrawl runs on `backend` Docker network, NOT `platform_net` | Container inspection + docker-compose.yaml read | `01-infrastructure.md` firecrawl row, `scraper.md` service doc |
| Firecrawl entire filesystem is `root:root` — devops-agent has no write access, cannot run git, cannot read `.env` | `ls -la /opt/firecrawl` output | `01-infrastructure.md` firecrawl row |
| Scraper `FIRECRAWL_API_URL` default is `http://firecrawl-api:3002` — hostname won't resolve cross-network | `services/scraper/api/app.py` | `scraper.md` service doc — deployment notes |
| Actual deployed `FIRECRAWL_API_URL` on svcnode-01 is UNKNOWN — root-owned `.env` is unreadable | Devops-agent access denial | Open task — verification required |
| Shogun repo on svcnode-01 is on `feature/gateway-pure-search-endpoints` | `git branch` on node | No doc currently captures deployment branch state |
| That feature branch has 2 commits NOT present in `main`: CORS fix + pure-search endpoints | `git log feature ^main` | No doc captures this drift |
| Logstack is intentionally NODE_ONLY at `/opt/logstack/` — not a git tracking gap | Node filesystem inspection + local repo comparison | `01-infrastructure.md` svcnode-01 section; service index |
| Logstack compose: Loki + Grafana on `logstack_net` bridge, Alloy scrapes Docker containers → Loki:3100 | `docker-compose.yml` and `alloy.hcl` read | Useful for any future logstack task |
| dbnode-01 runs PostgreSQL 17.7 (Debian 17.7-3.pgdg12+1) | Live `SELECT version()` | `01-infrastructure.md` dbnode-01 section |
| pg_stat_statements was NOT globally installed — required per-database install today | Live verification | `05-database.md` now corrected |
| pgcrypto is installed in `shogun_v1` only — no columns currently encrypted | Live verification | `05-database.md` now corrected |
| dba-agent has CREATEROLE + CREATEDB cluster privileges — previously undocumented | `SELECT rolcreaterole, rolcreatedb FROM pg_roles` | `05-database.md` now corrected |
| `settings.json` now exists at `.claude/settings.json` with SSH + git permission rules | Created this session | Project CLAUDE.md |

---

## 3. OPEN TASKS (carry-forward backlog, priority order)

**P1 — Immediate**

1. **Firecrawl URL verification**
   Confirm the actual `FIRECRAWL_API_URL` value in the scraper service's
   deployed `.env` on svcnode-01. The default value (`http://firecrawl-api:3002`)
   uses a hostname that won't resolve across Docker networks. The production
   URL must be using IP or host.docker.internal. Without confirmation, the
   scraper→firecrawl connection path is undocumented and unverified.

2. **Shogun feature branch assessment**
   `feature/gateway-pure-search-endpoints` has 2 unmerged commits on the
   svcnode-01 checkout vs. `main`. Decision needed: merge to main/develop,
   or treat the node as running experimental code intentionally. Either way,
   the branch state should be documented and the node brought to a known state.

**P2 — Near term**

3. **Firecrawl ownership transfer**
   `/opt/firecrawl` is root:root. devops-agent cannot manage it. This blocks
   any future firecrawl maintenance, upgrade, or config change. Transfer
   ownership to devops-agent or create a managed wrapper. Requires root
   access on svcnode-01 (out-of-band, not agent-executable).

4. **Firecrawl → platform_net network join**
   Firecrawl runs on `backend` network. Scraper is on `platform_net`. This
   network isolation means the scraper can't reach firecrawl by container
   hostname. Connecting firecrawl to `platform_net` would remove the
   host-port dependency and enable proper container name resolution.

5. **Reddit API service doc**
   Deployed 2026-03-02, still listed as "Docs Pending" in `_index.md`.
   Run `/register-service` to generate the service doc.

**P3 — Architecture / planning**

6. **Google Places decoupling architecture task**
   `platform_v1.places` (empty) vs `shogun_v1.places` (20 places, 60
   snapshots) are entangled. The routing ambiguity is documented as a
   holding note in `05-database.md`. Full decoupling requires an architecture
   decision on which service owns the canonical places dataset.

7. **Database ownership standardization**
   `shogun_v1` is owned by `postgres` (system superuser). Convention is
   application databases owned by `dba-agent`. Decision needed: migrate
   ownership or document the postgres ownership as intentional.

8. **PII data inventory**
   `pgcrypto` is installed in `shogun_v1` with intent for PII/auth column
   encryption, but no columns are currently encrypted. A PII inventory of
   `shogun_v1.public` tables (users, survey_votes) is needed before any
   PII handling policy can be enforced.

9. **MCP architecture decision**
   `mcp_shogun` is dormant — MCP deployment failed. `mcp_group` grants are
   in place. Whether to proceed with MCP, redesign it, or retire the role
   is an open architecture decision that blocks the mcp_group grants from
   having any purpose.

---

## 4. SUGGESTED CLAUDE.md ADDITIONS

The following text blocks could be added to the project `.claude/CLAUDE.md`
under a new "Known Infrastructure State" section inserted after the
Session Startup Protocol. This gives future agents startup awareness
without requiring full re-discovery on every session.

---

**Proposed section — insert after Session Startup Protocol:**

```markdown
## Known Infrastructure State — Last Verified 2026-03-06

This section captures confirmed infrastructure facts that future agents
should be aware of at session start. Update this section when the state
changes. Do not remove entries without verifying the state has changed.

### svcnode-01 Deployment State

- **Firecrawl** (`/opt/firecrawl`): root:root owned — devops-agent CANNOT
  read `.env`, run git commands, or modify configs. Runs on `backend` Docker
  network (NOT `platform_net`). Traefik does NOT proxy firecrawl.
  Host port 3002 is the access path. See: `01-infrastructure.md` exceptions table.

- **Scraper → Firecrawl URL**: Deployed `FIRECRAWL_API_URL` value is UNVERIFIED.
  Default code value (`http://firecrawl-api:3002`) will NOT work cross-network.
  Do not assume connectivity is working without checking the deployed `.env`.

- **Shogun checkout** (`/opt/git/work/shogun`): As of 2026-03-06, the working
  tree on svcnode-01 is on branch `feature/gateway-pure-search-endpoints` with
  2 commits not present in `main`. Deployment branch state is UNRESOLVED.

- **Logstack** (`/opt/logstack/`): Intentionally node-resident. Loki + Grafana
  + Grafana Alloy are deployed directly at `/opt/logstack/` and NOT tracked in
  the platform git repo. This is by design. Do not attempt to add logstack to
  the platform compose or repo.

### dbnode-01 Database State

- All 6 application databases are active (platform_v1, shogun_v1, mltrader,
  n8n, automation_sandbox_test)
- pg_stat_statements installed per-database (not global) — verified 2026-03-06
- pgvector 0.8.1 installed in platform_v1, shogun_v1, mltrader — verified 2026-03-06
- pgcrypto installed in shogun_v1 only — no columns currently encrypted
- dba-agent holds CREATEROLE + CREATEDB — UNAUTHORIZED_PROVISION hard block applies

### Open Architecture Decisions (Do Not Resolve Without Human Direction)

- Google Places routing: `platform_v1.places` vs `shogun_v1.places` — entangled
- MCP deployment: mcp_shogun dormant, mcp_group grants in place but unused
- Firecrawl network isolation: backend vs platform_net — connection path unverified
```

---

*End of reflection report.*
*All files reviewed read-only. No modifications made.*
