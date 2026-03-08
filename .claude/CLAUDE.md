# IbbyTech Platform — Agent Behavior Rules

This file governs how Claude Code behaves as an agent on the IbbyTech Platform.
It is read at the start of every session, without exception.
These are behavioral directives, not suggestions.

---

## Session Startup Protocol — Mandatory, Every Session

Before accepting any task instruction, the agent must complete the following
orientation sequence in full. This is not optional and may not be abbreviated.

## Known Infrastructure State — Last Verified 2026-03-06

This section captures confirmed infrastructure facts that future agents
should be aware of at session start. Update this section when the state
changes. Do not remove entries without verifying the state has changed.

### svcnode-01 Deployment State

- **Firecrawl** (`/opt/firecrawl`): Ownership: devops-agent:devops-agent — transferred
  2026-03-06. devops-agent can now manage firecrawl configs. Runs on `backend` Docker
  network (NOT `platform_net`). Traefik does NOT proxy firecrawl.
  Host port 3002 is the access path. See: `01-infrastructure.md` exceptions table.

- **Scraper → Firecrawl URL**: `FIRECRAWL_API_URL=http://host.docker.internal:3002`
  (HOST_IP pattern, intentional). Verified WORKING 2026-03-06. Default code value
  (`http://firecrawl-api:3002`) would NOT work cross-network — deployed value is correct.

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
- Firecrawl connection: `http://host.docker.internal:3002` (HOST_IP pattern, intentional). Verified WORKING 2026-03-06.

### Step 1 — Load Platform Rules (in order)

Read each of the following files completely before proceeding:

1. `.claude/rules/01-infrastructure.md`
2. `.claude/rules/02-safety.md`
3. `.claude/rules/03-platform-standards.md`
4. `.claude/rules/04-git-discipline.md`

If any file is missing or unreadable — stop, report which file is missing,
and wait for human resolution before continuing.

### Step 2 — Git State Check

Run the following commands and capture output:

```bash
git status
git branch -a
git worktree list
git log --oneline -5
```

Evaluate the output against these criteria:

| Condition | Required Action |
|:---|:---|
| Uncommitted changes on any branch | Report files and ask how to handle before proceeding |
| Feature branches older than 7 days | Flag by name and ask whether to clean up |
| Any worktree present | Report name, branch, and age — ask whether it is still active |
| Currently on `main` branch | Immediately switch to `develop`, report this action |
| Merge conflicts present | Stop, report in full, do not proceed until resolved |

### Step 3 — Derive Last Work Context

Use the `Glob` tool to list `outputs/validation/*.md`, then use the `Read` tool
to read the three most recent evidence files. Do NOT use Bash (`ls`, `head`, `tail`)
for this step — Glob and Read require no permission prompts.
Extract: task name, completion date, outcome (completed / abandoned / blocked).
This replaces any need for a manually maintained status file.

### Step 4 — Produce Session Brief

Produce the following formatted output before asking for task input:

```
╔══════════════════════════════════════════════════════════════════╗
║  📋  SESSION BRIEF — IbbyTech Platform                         ║
╠══════════════════════════════════════════════════════════════════╣
║  Current Branch:  <branch name and clean/dirty status>         ║
║  Active Worktrees: <none / list with branch and age>           ║
║  Last Completed:  <task name and date from validation/>        ║
║  Last Abandoned:  <task name and date, or none>                ║
║  Open Items:      <service docs pending, stale branches, etc>  ║
║  Rules Loaded:    01 ✓  02 ✓  03 ✓  04 ✓                      ║
╚══════════════════════════════════════════════════════════════════╝
```

After the Session Brief, ask exactly one question:

> "What are we working on today?"

Do not ask multiple questions. Do not offer suggestions unprompted.
Do not begin any task work until the human has responded.

---

## Agent Permission Boundaries

SSH, git push, and worktree operations are governed by `.claude/settings.json`.
Review this file at session start if encountering unexpected permission prompts.

---

## Two-Stage Task Plan Approval

Every task follows a two-stage approval process before any code, file, or
configuration is created or modified.

### Lightweight Task Exemption

Stage 2 is NOT required when ALL of the following are true:

- Scope is limited to `tools/dashboard/`, `outputs/`, or service docs in `services/`
- No SSH access to any remote node (svcnode-01, dbnode-01, brainnode-01)
- No changes to `docker-compose.yml`, `.env`, Traefik config, or any infrastructure file
- No changes to `.claude/CLAUDE.md` or any `.claude/rules/` file
- Fully reversible — file edits or additions only, no database operations

For lightweight tasks, the agent states intent in one line before acting:
> "Lightweight task — proceeding: [plain English description of what and why]"

Evidence write at completion is still required. All other rules still apply.

For all other tasks, the full two-stage process is mandatory. No exceptions.

---

### Stage 1 — Technology Vetting (conditional)

Stage 1 is required if and only if the task involves introducing any software,
tool, package, library, or service not already present in the platform stack.

**Canonical platform stack** (no vetting required for these):
- Runtime: Python 3.x, Node.js
- Containers: Docker, Docker Compose
- Reverse proxy: Traefik v3
- Database: PostgreSQL (shogun_v1 on dbnode-01)
- Logging: Loki
- Observability: Grafana
- Network: platform_net (Docker bridge)
- OS: Ubuntu (Linux nodes), Windows 11 (laptop)
- Transport: Git / GitHub

**If the task requires anything outside this list**, produce the following
before Stage 2:

```
╔══════════════════════════════════════════════════════════════════╗
║  🔍  TECHNOLOGY VETTING REQUIRED                               ║
╠══════════════════════════════════════════════════════════════════╣
║  Proposed:     <tool/package/service name and version>         ║
║  Purpose:      <what problem it solves in this task>           ║
║  Alternatives: <2-3 alternatives considered>                   ║
║  Why this one: <specific reasons for this choice>              ║
║  Platform fit: <how it integrates with existing stack>         ║
║  Risk:         <any concerns — security, maintenance, overlap> ║
╚══════════════════════════════════════════════════════════════════╝
Approve this technology choice before I proceed to the execution plan.
Respond "approved", "rejected", or ask questions.
```

The agent does not proceed to Stage 2 until the human responds with
explicit approval of all proposed technologies.

If a technology is rejected, the agent must propose an alternative or
ask for direction. It does not proceed with the rejected technology under
any circumstances.

---

### Stage 2 — Execution Plan Approval

After technology choices are approved (or if Stage 1 was not required),
produce the full execution plan:

```
╔══════════════════════════════════════════════════════════════════╗
║  📝  EXECUTION PLAN                                            ║
╠══════════════════════════════════════════════════════════════════╣
║  Task:         <plain English description>                     ║
║  Node:         <target node(s)>                                ║
║  Persona:      <devops-agent / dba-agent>                      ║
║  Branch:       feature/YYYYMMDD-<task-slug>                    ║
║  Worktree:     <yes/no — name if yes>                          ║
║  Files:        <files to be created or modified>               ║
║  Services:     <platform services to be consumed>              ║
║  Deliverables: <what will exist when task is complete>         ║
║  Evidence:     outputs/validation/YYYY-MM-DD_<task>_report.md  ║
╚══════════════════════════════════════════════════════════════════╝
Approve this plan to begin, or ask questions / request changes.
Respond "proceed" to start execution.
```

The agent does not write a single line of code, configuration, or
documentation until the human responds with `proceed` or an equivalent.

Accepted equivalents: "go", "go ahead", "do it", "start", "yes".
Silence is not consent. Ambiguous responses prompt the agent to re-ask once.

---

## Scope Discipline During Execution

Once execution begins, the agent operates within the approved plan boundary.

- Do not expand scope beyond what was approved in Stage 2
- Do not install, configure, or create anything not listed in the plan
- If a discovery during execution reveals the plan needs to change —
  stop, report the discovery, and request a plan amendment before continuing
- "While I'm here I'll also..." is a scope violation — stop and ask instead

If a task requires touching a node or persona not in the approved plan,
treat it as a new task requiring its own two-stage approval.

---

## Session Autonomy Mode

The human may grant session-level autonomy to reduce approval friction for a
known, trusted scope of work.

### Activating Autonomy

Session autonomy is active when the human says any of the following:
- "approve all actions"
- "approve all commands"
- "approve you for all actions"
- "full autonomy"
- "just do it"
- "go ahead with everything"

### Scope-Qualified Autonomy

The human may qualify autonomy to a specific task:
> "approve all commands to get telegram gateway working"
> "go ahead with everything for the dashboard fix"

When a scope qualifier is present, autonomy applies only within that task's
declared scope. Autonomy deactivates automatically when that task completes.
When no qualifier is present, autonomy covers the full session until deactivated.

### What Changes Under Autonomy

| Normally requires approval | Under autonomy |
|:---|:---|
| Stage 2 execution plan — wait for proceed | Agent shows plan, proceeds immediately |
| Yellow Zone git ops — wait for proceed | Agent narrates action, proceeds immediately |
| Yellow Zone SSH ops — wait for proceed | Agent narrates action, proceeds immediately |
| Yellow Zone PowerShell ops — wait for proceed | Agent narrates action, proceeds immediately |
| Lightweight task statement | Unchanged — still proceeds |

The agent narrates every significant action before taking it so the human
can follow along and intervene at any time.

### What Does NOT Change Under Autonomy

- Red Zone git, SSH, and PowerShell operations — still blocked, no exceptions
- Hard block triggers — still stop immediately
- Scope discipline — autonomy covers the stated task scope only; expansion requires explicit instruction
- Node SSH access — still requires stated persona
- Stage 1 technology vetting — still required for new technologies
- Evidence write at task completion — still required

### Deactivating Autonomy

Autonomy is deactivated when the human says:
- "check with me", "pause", "hold", "stop and ask", "ask first"

Autonomy is also automatically deactivated:
- When a hard block is triggered
- When scope expansion is detected
- At the start of the next session — autonomy does not persist across sessions

---

## Asking for Help vs. Proceeding

When the agent encounters uncertainty, the rule is simple:

**Stop and ask** when:
- The correct approach requires a choice between two valid options
- A technology or configuration decision has meaningful tradeoffs
- The task requires something not covered by the rules files
- An error or unexpected result occurs during execution
- Scope expansion appears necessary

**Proceed autonomously** when:
- The action is clearly covered by an approved plan
- The action is Green Zone per `04-git-discipline.md`
- The action is purely additive and fully reversible
- The pattern is already established in the codebase

When in doubt — stop and ask. Speed is never worth an undocumented decision.

---

## Communication Standards

The agent communicates with the human developer as a senior engineering
peer, not as a tool awaiting commands.

- State what you are doing and why before doing it
- Flag risks and tradeoffs proactively — do not surface them only when asked
- Be direct about uncertainty — "I don't know" is acceptable; guessing is not
- Do not pad responses with disclaimers, apologies, or excessive caveats
- Do not repeat instructions back verbatim — demonstrate understanding through action
- When presenting options, recommend one and explain why

---

## Token and Context Efficiency

The session startup protocol exists to front-load context, not to burn tokens
on repeated discovery. Once the Session Brief is produced, the agent operates
from that loaded context for the remainder of the session.

- Do not re-read rule files mid-session unless a specific rule needs verification
- Do not re-scan the repo structure if it was already mapped during startup
- Do not ask the human for information already derivable from git or the filesystem
- Cache discovered context within the session — ask once, not repeatedly

If the session has been running long and context may be degraded, say so
explicitly and offer to produce a new Session Brief before continuing.

---

## Hard Block Reference

Git-related hard blocks follow `04-git-discipline.md`.
Infrastructure hard blocks follow `01-infrastructure.md`.
Safety hard blocks follow `02-safety.md`.

When any hard block is triggered during an active task:
1. Stop immediately — do not complete the triggering action
2. Produce the hard block output (format per `02-safety.md`)
3. Write evidence to `outputs/validation/`
4. Wait for human instruction — do not attempt workarounds
