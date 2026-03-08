# svcnode-01 Discovery Audit Report
**Date:** 2026-03-06
**Branch:** feature/20260306-svcnode01-drift-remediation
**Persona:** devops-agent
**Node:** svcnode-01 (192.168.71.220)

---

## Purpose

Four targeted discovery checks to resolve open items flagged in
`2026-03-06_svcnode01-git-sync-audit.md`:

- Check 1: Logstack reconciliation — NODE_ONLY determination
- Check 2: Shogun feature branch merge status
- Check 3: Firecrawl dependency mapping
- Check 4: Focalboard classification and _index.md entry

---

## Check 1 — Logstack: Local Repo vs Node Composition

**Question:** The local `infra/compose/docker-compose.infra.yml` does not define
loki, grafana, or alloy containers. What runs on the node?

**Local repo finding:**
`infra/compose/docker-compose.infra.yml` defines only:
- `traefik` service (container_name: platform-traefik)
- `platform_net` bridge network

No loki, grafana, or grafana-alloy services are defined in the tracked repo.

**Node finding — /opt/logstack/:**
Three config files exist at `/opt/logstack/` (node-only, not in git):
- `docker-compose.yml` — defines `loki` and `grafana` services (Loki official image,
  Grafana 11.2.0, both on `logstack_net` bridge network)
- `loki-config.yml` — Loki storage and schema config (BoltDB shipper, filesystem chunks)
- `alloy.hcl` — Grafana Alloy config (scrapes logs from Docker containers, forwards to
  Loki at `loki:3100`)

**Classification: NODE_ONLY**
The logstack (Loki + Grafana + Grafana Alloy) is deployed and managed directly on
svcnode-01 at `/opt/logstack/`. It is not tracked in the platform git repository.
This is intentional — the compose file and configs are node-resident infrastructure,
not platform application code.

**Status: DOCUMENTED** — service docs already exist in `.claude/services/loki.md`
and `.claude/services/grafana.md`. No git tracking is required for node-resident
infrastructure configs.

---

## Check 2 — Shogun Feature Branch Merge Status

**Question:** Is `feature/gateway-pure-search-endpoints` merged into `main` on svcnode-01?

**Finding:**
```
git log feature/gateway-pure-search-endpoints ^main --oneline
caab728 fix(gateway): apply CORS to sub-apps to fix OPTIONS preflight failures
292fa7d feat(gateway): implement pure-search endpoints for Place Search and Nearby Search
```

**Result: NOT_MERGED**
Two commits on `feature/gateway-pure-search-endpoints` are absent from `main`:
- `caab728` — CORS fix for OPTIONS preflight
- `292fa7d` — pure-search endpoint implementation

The svcnode-01 `/opt/git/work/shogun` working tree is checked out on a feature branch
that has not been merged to main. This constitutes a deployment drift — the node is
running code that has no equivalent in any protected branch.

**Action required:** Separate task — assess whether these commits should be merged
to shogun main/develop or whether the feature branch represents abandoned work.
This discovery report does not make that determination.

---

## Check 3 — Firecrawl Dependency Map

**Question:** How does the scraper service communicate with firecrawl? Is firecrawl
on platform_net, or accessed via host port?

### 3a. Firecrawl Containers

Three containers running under `/opt/firecrawl/docker-compose.yaml`:
```
firecrawl-api-1     Up 26h    0.0.0.0:3002->3002/tcp
firecrawl-worker-1  Up 26h    (no ports)
firecrawl-redis-1   Up 2d     (no ports)
```

All containers are root:root owned (legacy exception — documented in `01-infrastructure.md`).

### 3b. Firecrawl Docker Network

`/opt/firecrawl/docker-compose.yaml` defines a `backend` network. The three containers
join `backend` only. They do NOT join `platform_net`.

`firecrawl-api-1` exposes port 3002 on the host: `0.0.0.0:3002->3002/tcp`.

No Traefik routing rules reference firecrawl — it is not behind the reverse proxy.

### 3c. Scraper → Firecrawl Connection Path

Platform repo `services/scraper/api/app.py` references:
```
FIRECRAWL_API_URL default: http://firecrawl-api:3002
```

Platform repo `services/scraper/docker-compose.yml` has a comment referencing
`/opt/firecrawl` as the upstream source.

**Resolution:**
When scraper runs on svcnode-01 in a Docker container connected to `platform_net`,
`firecrawl-api` hostname would NOT resolve (firecrawl is on `backend`, not `platform_net`).
Connection must occur via host port 3002 using the node's IP or `host.docker.internal`.

The default `FIRECRAWL_API_URL=http://firecrawl-api:3002` would fail in production
if the scraper container is not on the same `backend` network as firecrawl.

**Finding: DEPENDENCY GAP**
The scraper service's `FIRECRAWL_API_URL` default value assumes container hostname
resolution (`firecrawl-api`), but firecrawl's `backend` network is separate from
`platform_net`. The actual runtime URL used in `.env` on the node was not captured
(root-owned `.env` at `/opt/firecrawl/.env` — cannot read as devops-agent).

This should be verified: does the scraper's deployed `.env` set `FIRECRAWL_API_URL`
to `http://192.168.71.220:3002` or `http://localhost:3002`?

**Action required:** Separate task — verify scraper `.env` on svcnode-01, confirm
actual `FIRECRAWL_API_URL` value, and document network topology in scraper service doc.

### 3d. Traefik Routing

No Traefik labels or routing rules reference firecrawl. Firecrawl is not externally
accessible through Traefik. Host-port exposure only.

---

## Check 4 — Focalboard Classification

**Question:** What is focalboard? Does it belong in the platform service index?

**Finding:**
Focalboard is a self-hosted project management / kanban board application
(Mattermost open-source project). It runs on svcnode-01.

**Classification: NON-PLATFORM TOOL**
Focalboard is not a platform API gateway or shared infrastructure service.
It is a standalone project management UI — not consumed by other services,
not exposed via platform APIs, not relevant to agent task routing decisions.

It belongs in a separate "Non-Platform Tools" section in `_index.md` for
inventory completeness, not in the Active Services table.

**Action taken:** Added "Non-Platform Tools" section to `.claude/services/_index.md`
with focalboard entry.

---

## Summary Table

| Check | Item | Finding | Status |
|:---|:---|:---|:---|
| 1 | Logstack | NODE_ONLY — intentional, not tracked in git | Documented |
| 2 | Shogun feature branch | NOT_MERGED — 2 commits missing from main | Action required |
| 3 | Firecrawl network topology | backend network separate from platform_net; scraper URL gap | Action required |
| 4 | Focalboard | Non-platform tool — added to _index.md inventory | Complete |

---

## Open Items from This Audit

1. **Shogun feature branch** — `feature/gateway-pure-search-endpoints` has 2 unmerged
   commits on svcnode-01's shogun checkout. Requires separate task to assess
   merge status and determine intended state.

2. **Scraper → Firecrawl URL** — Scraper `.env` `FIRECRAWL_API_URL` value not confirmed.
   The `backend` vs `platform_net` network separation creates a potential misconfiguration
   that should be validated against the deployed `.env` on svcnode-01.

---

## Evidence Scope

This is a read-only discovery report. No schema changes, no infrastructure changes.
Only `_index.md` was modified (focalboard non-platform entry added, committed to
`feature/20260306-svcnode01-drift-remediation`).
