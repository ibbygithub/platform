# IbbyTech Platform — Claude Code Briefing

## What This Repo Is
This is the **IbbyTech Platform** repository — the single source of truth for shared
infrastructure, enterprise services, and engineering standards across all IbbyTech projects.

Every project under `C:\git\work\<project>` references this repo for platform context.
On Linux nodes, the equivalent path is `/opt/git/work/<project>`.

---

## The Three-Node Architecture

You are working within a purpose-built three-node execution environment.
Each node has a strict role. Never mix responsibilities across nodes.

| Node | Address | Role | What Lives Here |
|:---|:---|:---|:---|
| **svcnode-01** | `192.168.71.220` | Docker Platform | All Docker containers, API gateways, Traefik, enterprise services |
| **dbnode-01** | `192.168.71.221` | Database Tier | PostgreSQL `shogun_v1` only. No Docker. No applications. |
| **brainnode-01** | `192.168.71.222` | Application Runtime | Main apps, MCP servers, cron jobs, ETL scripts. No Docker. |

**Control Plane:** `ibbytech-laptop` (Windows 11) — all coding happens here.
Transport to nodes is **Git only** (push/pull). Never SCP, SFTP, or rsync.

---

## Enterprise Services First

Before building any new capability, check `.claude/services/_index.md`.

If a service already exists on `svcnode-01` — a gateway, an API proxy, a scraping
service — **consume it**. Do not duplicate infrastructure. This is not a suggestion;
it is a platform standard.

Current enterprise services include: Google Places, Telegram Bot, LLM Gateway,
Firecrawl (web scraping), Loki (logging), Grafana (observability).
See the service index for consumption details.

---

## Identity and Access

Two personas cover all remote access. Never improvise credentials.

| Persona | Account | Key File | Authorized Nodes |
|:---|:---|:---|:---|
| **DevOps Agent** | `devops-agent` | `~/.ssh/devops-agent_ed25519_clean` | `svcnode-01`, `brainnode-01` |
| **DBA Agent** | `dba-agent` | `~/.ssh/dba-agent_ed25519` | `dbnode-01` only |

If a task requires access to a node and neither persona covers it — **stop and ask**.
Do not use any other SSH identity found on the system.

---

## Development Workflow

1. **Code on Windows:** Work in `C:\git\work\<project>`. Commit to `feature/<name>`.
2. **Transport via Git:** Push to GitHub. Pull on target node.
3. **Execute on Linux:** SSH to target node → `git pull` → start service.

---

## Observability Standard

All services must emit structured logs to Loki. All API gateway calls must be logged.
This supports billing, troubleshooting, security auditing, and support.
If you write a service that does not log to Loki, flag it as incomplete.

---

## Reference Files

- Node roles and persona rules: `.claude/rules/01-infrastructure.md`
- Safety and evidence rules: `.claude/rules/02-safety.md`
- Platform standards: `.claude/rules/03-platform-standards.md`
- Service index: `.claude/services/_index.md`
- Service doc template: `templates/service-doc-template.md`
