# Plan: IbbyTech Foundation + Shogun Bootstrap
Date: 2026-03-12
Status: Approved

## Objective

Create `ibbytech-foundation` as the single source of truth for Claude Code
engineering standards across all IbbyTech projects. Scaffold the Shogun project
as the first consumer of that foundation. Establish `/start-session` as a
universal, user-level startup command available in every project session on
this machine.

The outcome: starting Claude in any IbbyTech project folder and running
`/start-session` produces the full session brief — security scan, git state,
planning backlog, known infrastructure context — without project-specific
setup or duplication.

---

## Scope

**Included:**
- Create and populate `ibbytech-foundation` repo
- Create `/start-session` user-level command at `~/.claude/commands/`
- Scaffold Shogun project: `.claude/CLAUDE.md`, `settings.json`, `outputs/` structure,
  `planning-state.md` initialized from known Shogun context
- Verify the full startup sequence works from the Shogun project directory

**Explicitly out of scope:**
- Refactoring the platform project to use the foundation (separate task, post-Shogun)
- Any Shogun application code, Docker services, or deployment work
- mltrader or any other future project
- brainnode-01 onboarding
- Advanced Planner skill migration (addressed in Phase 1 notes below)

---

## Current State

- Platform project has mature rules (01-05), CISO skill, dbnode skill, templates,
  settings.json, and service docs — all locked to platform paths and working
  correctly in platform sessions
- Shogun project folder at `C:\git\work\shogun\` exists with code but has no
  `.claude\` directory, no planning state, no settings.json
- `~/.claude/commands/` is available but has no start-session command
- `--add-dir ../platform` from Shogun does not produce a full session brief
  because the platform startup protocol references platform-specific paths
  (preflight script, validation outputs, worktrees) that don't exist in Shogun

The root problem: the startup protocol is tangled with platform-specific
infrastructure. The fix is to move it into a path-agnostic command.

---

## Architecture Decisions

### Why a separate ibbytech-foundation repo (not user-level ~/.claude/)

`~/.claude/` is for machine-level configuration and commands. The foundation
is engineering content — rules, skills, templates — that should be version-
controlled, diffable, and potentially shareable. A dedicated repo at
`C:\git\work\ibbytech-foundation\` gives us git history, rollback, and a
clean separation between "how Claude behaves on this machine" (user config)
and "how IbbyTech engineering works" (the foundation).

### Why /start-session lives at ~/.claude/commands/

The command is identical across all projects. Placing it at user level means
zero per-project maintenance. When the startup protocol improves, one file
update propagates everywhere. Scaffolding a copy per project would create
the exact divergence problem we're solving.

### Path convention this design depends on

All IbbyTech projects live at `C:\git\work\<project-name>\`. This is a
documented convention. The /start-session command uses the relative path
`../ibbytech-foundation/` which resolves correctly from any project folder
at that depth. This convention must be maintained. A project nested deeper
would require path adjustment.

### What moves to foundation vs. stays in platform

**Moves to foundation** — homelab-wide, project-agnostic:
- Rules 01-05 (adapted — see Phase 1 notes)
- CISO skill, dbnode skill
- Service doc template, evidence report template, settings baseline
- Advanced Planner skill (currently at `~/.claude/skills/` — should be in
  foundation for version control; user-level copy can remain as fallback)

**Stays in platform** — platform-specific:
- Platform CLAUDE.md (platform session protocol, known infrastructure state,
  platform-specific startup like preflight script)
- Service docs (`.claude/services/`)
- `/register-service` command (references platform paths)
- Validation and planning outputs
- Service source code and validate scripts

**Moves to /start-session command** — was in platform CLAUDE.md startup
protocol, now path-agnostic:
- Git state check (Steps 2 and 2.6)
- Security scan (Trigger Point 1 CISO checks)
- Last work context (reads from project-local outputs/validation/)
- Session Brief production
- Planning state read (from project-local outputs/planning/planning-state.md)

---

## Phases

### Phase 0 — Create ibbytech-foundation repo

**Goal:** Empty repo with folder structure exists at `C:\git\work\ibbytech-foundation\`
and is pushed to GitHub.

**Entry criteria:** None — this is the first step.

**Deliverables:**
```
C:\git\work\ibbytech-foundation\
├── .claude\
│   ├── CLAUDE.md          # Minimal descriptor (see content spec below)
│   └── rules\             # Empty — populated in Phase 1
├── skills\                # Empty — populated in Phase 1
└── templates\             # Empty — populated in Phase 1
```

**Foundation CLAUDE.md content spec** (minimal — NO startup protocol):
```
# IbbyTech Foundation — Shared Engineering Standards

This directory is the single source of truth for engineering rules, skills,
and templates across all IbbyTech projects.

## Usage
Add to any project session:
  claude --add-dir ../ibbytech-foundation

## Contents
- .claude/rules/   — Rules 01-05 (infrastructure, safety, standards, git, database)
- skills/          — CISO security, dbnode-01, advanced-planner
- templates/       — service-doc, evidence-report, openapi skeleton, settings baseline

## Behavioral Rules
The following apply to all projects that reference this foundation.
[Rules content from platform's 02-safety.md, two-stage approval, autonomy model,
communication standards, hard block format — see Phase 1 for exact migration]
```

**Git:** `git init`, initial commit, create GitHub repo `ibbytech-foundation`,
push. Branch: `main` (this repo uses `main` as default — no develop branch needed
for a standards repo, promotion happens directly).

**Exit criteria:** Repo exists on GitHub. `git remote -v` shows origin. Folder
structure created. Initial commit present.

**Complexity:** Low
**Dependencies:** None

---

### Phase 1 — Populate foundation from platform

**Goal:** All 5 rules files, both skills, and all templates exist in foundation,
adapted as specified. Foundation CLAUDE.md contains the behavioral rules section.

**Entry criteria:** Phase 0 complete.

**Deliverables:**

```
.claude/
  CLAUDE.md          — Complete behavioral rules (see spec)
  rules/
    01-infrastructure.md  — Copy as-is (node IPs are homelab-wide, not platform-specific)
    02-safety.md          — Copy as-is
    03-platform-standards.md  — Adapted (3 changes, see below)
    04-git-discipline.md  — Copy as-is
    05-database.md        — Copy as-is
skills/
  ciso-security.md        — Copy from platform/.claude/skills/ciso-security.md
  dbnode-01-skill.md      — Copy from platform/.claude/skills/dbnode-01-skill.md
  advanced-planner.md     — Copy from ~/.claude/skills/advanced-planner/ (consolidate)
templates/
  service-doc-template.md     — Copy from platform/templates/service-doc-template.md
  evidence-report-template.md — New (see spec below)
  openapi-template.yaml       — New (OpenAPI 3.1.0 skeleton)
  project-claude-md-template.md — New (template for new project CLAUDE.md files)
  settings-baseline.json      — Copy from platform/.claude/settings.json
```

**03-platform-standards.md adaptations (3 targeted changes only):**

1. Section "Enterprise Services First" — change `.claude/services/_index.md`
   reference to `../platform/.claude/services/_index.md`. The rule stays; the
   path becomes explicit about where to look.

2. Section "Service Documentation" — replace references to `templates/` with
   `../ibbytech-foundation/templates/`. Service docs still live in the consuming
   project; the templates come from foundation.

3. Section "Referencing This Platform Repo From Other Projects" — replace entirely
   with "Referencing IbbyTech Foundation":
   ```
   In any project's CLAUDE.md, include:
     ## Foundation Reference
     Engineering standards: ../ibbytech-foundation
     Launch command: claude --add-dir ../ibbytech-foundation
   ```

   Do NOT change any other content in 03. Node paths, service references,
   observability requirements, and env var rules are all homelab-wide.

**Foundation CLAUDE.md behavioral section** — migrate from platform CLAUDE.md:
- Two-Stage Task Plan Approval (Stage 1 vetting + Stage 2 execution plan)
- Lightweight Task Exemption
- Stage 3 Delivery Gate (Green Gate 7-item checklist)
- Session Autonomy Model
- Asking for Help vs. Proceeding
- Communication Standards
- Hard Block Reference
- Token and Context Efficiency note

Do NOT migrate to foundation CLAUDE.md:
- Session Startup Protocol (Step 1-4) — this moves to /start-session command
- Known Infrastructure State — this belongs in each project's CLAUDE.md
- Agent Permission Boundaries note (platform-specific)

**New: evidence-report-template.md spec:**
Standard header block for all evidence reports:
```
# Evidence Report — [Task Name]
Date: YYYY-MM-DD
Branch: [branch name]
Task: [plain English task description]
Node(s): [nodes touched, or "laptop only"]
Persona(s): [devops-agent / dba-agent / none]

## Objective
## Actions Taken
## Verification
## Green Gate Checklist
## Outcome
```

**New: openapi-template.yaml spec:**
OpenAPI 3.1.0 skeleton with placeholder servers (FQDN + internal Docker),
standard health endpoint, example POST endpoint, and schema components section.

**New: project-claude-md-template.md spec:**
Template that new project CLAUDE.md files are created from. Contains:
- Project identity section (fill in)
- Known Infrastructure State section (fill in)
- Node/Persona assignments section (fill in)
- Foundation Reference block (static — same for all projects)
- Session Startup note: "Run /start-session at the start of every session"
- Platform services consumed section (fill in)
- Open Architecture Decisions section (fill in)

**Exit criteria:** All files present. No broken references. `03-platform-standards.md`
adaptations verified by reading the three changed sections. Commit and push to foundation main.

**Complexity:** Medium (careful adaptation of 03, new templates)
**Dependencies:** Phase 0

---

### Phase 2 — Create /start-session user-level command

**Goal:** `~/.claude/commands/start-session.md` exists and produces the full
session brief when invoked from any IbbyTech project directory.

**Entry criteria:** Phase 1 complete (command references foundation paths).

**Deliverable:** `C:\Users\toddi\.claude\commands\start-session.md`

**Command execution sequence** (what the command instructs Claude to do):

**Step 1 — Load foundation rules**
Read these files using the Read tool. Use relative path `../ibbytech-foundation/`
from the current project directory:
- `../ibbytech-foundation/.claude/rules/01-infrastructure.md`
- `../ibbytech-foundation/.claude/rules/02-safety.md`
- `../ibbytech-foundation/.claude/rules/03-platform-standards.md`
- `../ibbytech-foundation/.claude/rules/04-git-discipline.md`
- `../ibbytech-foundation/.claude/rules/05-database.md`

**Step 2 — Security scan (CISO Trigger Point 1)**
Run these 4 commands autonomously (Green Zone):
```bash
git ls-files | grep -i "\.env"
cat .gitignore | grep -i env
git log --oneline -20 | grep -iE "env|secret|token|key|credential|password"
git ls-files services/ | grep -i "\.env"
```
(Note: last command may return nothing if no services/ dir — that is fine)

**Step 3 — Git state check**
Run these 4 commands autonomously (Green Zone):
```bash
git status
git branch -a
git worktree list
git log --oneline -5
```

Evaluate against the standard criteria table from 04-git-discipline.md.

**Step 4 — Conditional preflight**
If `tools/test-harness/platform_preflight.py` exists in the current directory,
run: `python tools/test-harness/platform_preflight.py`
If it does not exist, skip and note "No preflight script — skipped" in the brief.

**Step 5 — Last work context**
Use Glob to list `outputs/validation/*.md`. Read the 3 most recent files.
Extract: task name, date, outcome. If no validation files exist, note "First session
— no prior validation history."

**Step 6 — Planning state**
Read `outputs/planning/planning-state.md`. If it does not exist, note "No planning
state found — this may be a new project or planning has not started."

**Step 7 — Produce Session Brief**
```
╔══════════════════════════════════════════════════════════════════╗
║  📋  SESSION BRIEF — [Project Name from CLAUDE.md or CWD name] ║
╠══════════════════════════════════════════════════════════════════╣
║  Current Branch:  <branch and clean/dirty status>              ║
║  Active Worktrees: <none / list with branch>                   ║
║  Last Completed:  <task and date from validation/>             ║
║  Last Abandoned:  <task and date, or none>                     ║
║  Open Items:      <stale branches, pending decisions, etc>     ║
║  Rules Loaded:    01 ✓  02 ✓  03 ✓  04 ✓  05 ✓               ║
║  Preflight:       <PASS / FAIL details / skipped>              ║
║  🔐 Security:     .env tracked: <none ✓ / FLAGGED: filename>  ║
║                   .gitignore:   <covered ✓ / MISSING>         ║
║                   Log hits:     <none ✓ / review: ref>        ║
╚══════════════════════════════════════════════════════════════════╝
```

**Step 8 — Ask one question**
> "What are we working on today?"

Do not offer suggestions. Do not begin work. Wait for human response.

**Exit criteria:** Command file exists. Invoked from Shogun directory (Phase 4)
produces a complete Session Brief with all 8 sections populated correctly.

**Complexity:** Medium (prompt engineering for path-agnostic execution)
**Dependencies:** Phase 1

---

### Phase 3 — Scaffold Shogun project

**Goal:** Shogun has a complete `.claude/` setup and initialized `outputs/`
structure. Running `/start-session` with `--add-dir ../ibbytech-foundation`
in Shogun will produce a project-aware session brief.

**Entry criteria:** Phase 1 complete (need settings baseline). Phase 2 not
required — can run in parallel with Phase 2.

**Pre-execution check:** Before writing any files, run `git status` in Shogun
to assess current branch state. The known state from platform planning notes
is that svcnode-01 has a checkout on `feature/gateway-pure-search-endpoints`
with 2 unmerged commits — but the **laptop's** Shogun repo state needs to be
confirmed before scaffolding.

**Deliverables:**

**`.claude/CLAUDE.md`** — Shogun-specific (use project-claude-md-template.md as base):
```
# Project Shogun — Agent Behavior Rules

## Foundation Reference
Engineering standards: ../ibbytech-foundation
Launch command: claude --add-dir ../ibbytech-foundation

## Session Startup
Run /start-session at the start of every session.
Rules and behavioral directives are loaded from ../ibbytech-foundation.

## Project Identity
- Project: Shogun — AI travel concierge for Japan trips
- Users: Family (~3 users)
- Node (app): svcnode-01 — Docker containers via devops-agent
- Node (db): dbnode-01 — shogun_v1 database via dba-agent
- brainnode-01: Not yet onboarded — not a target node for this project yet

## Platform Services Consumed
- Google Places gateway: place search, neighborhood anchors
- LLM gateway: completions via Gemini 2.0 Flash
- Telegram gateway: bot interface to end users
- Reddit gateway: available if Shogun needs Reddit data

## Database Routing
- Primary database: shogun_v1 on dbnode-01
- Schema: public (Shogun owns this schema)
- App user: [to be confirmed at first DB task]
- Google Places data: DO NOT write to shogun_v1 — read via Places REST gateway
  (platform_v1.places is canonical — resolved 2026-03-12)

## Known Infrastructure State — Last Verified 2026-03-12
- svcnode-01 Shogun checkout: branch `feature/gateway-pure-search-endpoints`
  with 2 commits not present in main. Deploy branch state UNRESOLVED.
  Must be resolved before any new Shogun service is deployed.
- dbnode-01: shogun_v1 active. places schema DROPPED 2026-03-12.
  All place data now via platform_v1.places through REST gateway.
- brainnode-01: no Shogun workloads. SSH key and git permissions
  not yet provisioned for this node.

## Open Architecture Decisions
- Shogun deploy branch resolution: feature/gateway-pure-search-endpoints
  has 2 unmerged commits on svcnode-01. Decision needed before deployment.
- MCP tool calling: deferred to OpenRouter planning session. Shogun uses
  direct REST calls for now. No MCP tool calling in Shogun until post-MVP.
- Gemini 2.0 Flash is the current LLM. Model switch requires approval.

## Technology Registry (Approved)
- Runtime: Python 3.x / FastAPI
- LLM: Gemini 2.0 Flash (via LLM gateway)
- Interface: Telegram bot
- Database: PostgreSQL 17 / shogun_v1
- Transport: Direct REST calls to platform services
```

**`.claude/settings.json`** — copy from `ibbytech-foundation/templates/settings-baseline.json`
with one addition: the `cd C:/git/work/platform` patterns become `cd C:/git/work/shogun`
patterns. Specifically, add a Shogun-equivalent block:
```json
"Bash(cd C:/git/work/shogun && git status*)",
"Bash(cd C:/git/work/shogun && git log*)",
"Bash(cd C:/git/work/shogun && git diff*)",
"Bash(cd C:/git/work/shogun && git show*)",
"Bash(cd C:/git/work/shogun && git branch*)",
"Bash(cd C:/git/work/shogun && git add*)",
"Bash(cd C:/git/work/shogun && git commit*)",
"Bash(cd C:/git/work/shogun && git stash*)",
"Bash(cd C:/git/work/shogun && git fetch*)",
"Bash(cd C:/git/work/shogun && git checkout*)",
"Bash(cd C:/git/work/shogun && git switch*)",
"Bash(cd C:/git/work/shogun && git worktree*)",
"Bash(cd C:/git/work/shogun && git merge*)",
"Bash(cd C:/git/work/shogun && git push*)",
"Bash(cd C:/git/work/shogun && git tag*)",
"Bash(cd C:/git/work/shogun && ls*)",
"Bash(cd C:/git/work/shogun && cat*)",
"Bash(cd C:/git/work/shogun && python*)",
"Bash(cd C:/git/work/shogun && pip*)"
```

**`outputs/planning/planning-state.md`** — initialized with Shogun context:
```
# Planning State — Project Shogun
Last updated: 2026-03-12 (initial — bootstrapped from platform planning history)

## Project Summary
Shogun is an AI travel concierge service for Japan trips (family use, ~3 users).
Builds on IbbyTech platform services. Primary interface: Telegram bot. Backend:
FastAPI on svcnode-01. LLM: Gemini 2.0 Flash. Data: shogun_v1 on dbnode-01.
Platform services consumed: Google Places, LLM gateway, Telegram, Reddit (planned).

## Active Work
| Item | Description | Phase | Status | Last Updated |
|------|-------------|-------|--------|--------------|
| Project bootstrap | .claude setup, foundation link, planning state | Phase 0 | Complete | 2026-03-12 |

## Open Decisions
- Deploy branch resolution: svcnode-01 Shogun checkout on
  feature/gateway-pure-search-endpoints with 2 unmerged commits.
  Must resolve before any new deployment. Options: merge to main,
  cherry-pick, or reset to main and re-apply.
- MCP tool calling: deferred to OpenRouter planning session.
  No MCP in Shogun until post-MVP and OpenRouter architecture is decided.

## Technology Registry
| Technology | Role | Rationale | Date |
|------------|------|-----------|------|
| Python 3.x / FastAPI | Service runtime | Platform standard | 2026-02-15 |
| Gemini 2.0 Flash | LLM completions | Strong results, low cost, multimodal | 2026-03-09 |
| Telegram bot | User interface | Low-friction family interface | 2026-03-09 |
| PostgreSQL 17 / shogun_v1 | Application database | Platform standard | 2026-02-15 |

## Decision Log

### Google Places routing — 2026-03-12
- Decision: Shogun does NOT write place data to shogun_v1. Reads via Places REST gateway.
- platform_v1.places is canonical. shogun_v1.places schema dropped.
- Source: platform planning session 2026-03-12.

### MCP protocol strategy — 2026-03-09
- Decision: Shogun uses direct REST calls during MVP. MCP deferred post-MVP.
- Option C (LLM gateway tool orchestration) deferred to OpenRouter planning session.
- Risk accepted: No MCP tool calling in Shogun until after MVP is stable.

## Backlog
- Shogun reboot: FastAPI service + Telegram interface on svcnode-01.
  Features: weather, blossom tracking, local news, calendar, lodging/contacts/itinerary.
- Expense tracking: Web page in Shogun app. Image OCR via Gemini multimodal.
  Deferred to Shogun Phase 2.
- Location-aware geofencing: Alert when near saved location.
  Requires memory entity model. Design during Memory MCP vetting session.

## Planning Documents
| Document | Path | Status |
|----------|------|--------|
| (none yet) | | |
```

**`outputs/validation/.gitkeep`** — empty file to track the directory in git.

**Exit criteria:** All files created. Git status in Shogun shows new files.
Files readable with correct content.

**Complexity:** Low
**Dependencies:** Phase 1 (settings baseline)

---

### Phase 4 — Verify Shogun session startup

**Goal:** Confirm that starting Claude in Shogun with the foundation link and
running `/start-session` produces a complete, accurate session brief.

**Entry criteria:** Phases 2 and 3 complete.

**Verification steps:**

1. In a new terminal, navigate to `C:\git\work\shogun\`
2. Start Claude: `claude --add-dir ../ibbytech-foundation`
3. Run `/start-session`
4. Confirm each section of the Session Brief is populated:
   - Rules Loaded: 01-05 all checked
   - Security scan: no .env tracked, .gitignore covered
   - Git state: correct branch shown
   - Preflight: "skipped" (no preflight script in Shogun)
   - Last work: shows Phase 3 scaffolding work or "first session" message
   - Planning state: Shogun planning state loaded correctly

**Pass criteria:** All 8 sections of the Session Brief present. No path errors.
No "file not found" messages for foundation rules. Planning state reflects
Shogun context, not platform context.

**Complexity:** Low
**Dependencies:** Phases 2 and 3

---

## Risks

**Risk: Path convention break**
If a project is ever created at a different depth (e.g., `C:\git\work\clients\shogun\`),
the `../ibbytech-foundation/` relative path breaks.
Likelihood: Low (convention is documented and enforced).
Impact: High (silent failures in rule loading).
Mitigation: Document the depth requirement explicitly in the foundation CLAUDE.md.
Status: Open — accepted for now given single-developer homelab context.

**Risk: Foundation diverges from platform rules**
If platform rules (01-05) evolve but foundation is not updated, they drift.
Likelihood: Medium (platform is actively developed).
Impact: Medium (projects using foundation get stale rules).
Mitigation: After this task, refactor platform to reference foundation rules
rather than maintaining its own copies (separate task). Until then, foundation
must be manually kept in sync when platform rules change.
Status: Open — requires follow-up task.

**Risk: Shogun existing git state is messy**
The platform planning state notes the svcnode-01 checkout is on an unmerged
feature branch. The laptop's Shogun repo state is unknown.
If the laptop repo has stale branches, uncommitted changes, or conflicts,
scaffolding on top of that creates confusion.
Likelihood: Unknown (not yet checked).
Impact: Medium.
Mitigation: Phase 3 pre-execution check confirms git state before writing any files.
Status: Flagged — execution agent must check before scaffolding.

**Risk: /start-session command path fails for services/ security scan**
The command runs `git ls-files services/ | grep -i "\.env"` — if Shogun has
no `services/` directory, this returns nothing (not an error). Fine.
If Shogun has a differently named directory, coverage is incomplete.
Likelihood: Low.
Mitigation: The command notes this as informational, not a hard fail.
Status: Accepted.

---

## Open Items

None blocking execution. Post-execution follow-up:

1. **Platform refactor** — update platform CLAUDE.md to use /start-session
   and reference foundation rules instead of maintaining its own copies.
   Separate task, post-Shogun stabilization.

2. **New project scaffolder command** — a `/new-project` command that automates
   Phase 3 for any new project. Out of scope here; the scaffolding steps
   are documented precisely enough to be done manually for Shogun, and the
   pattern can be extracted into a command after a second project is bootstrapped.

3. **Foundation repo maintenance discipline** — when any rules file in platform
   changes, mirror the change to foundation. This is a manual process until
   the platform refactor (item 1) eliminates the duplication.

---

## Execution Sequence

```
Phase 0: Create ibbytech-foundation repo          [~10 min]
Phase 1: Populate foundation from platform        [~20 min]
Phase 2: Create /start-session command            [~15 min]
Phase 3: Scaffold Shogun                          [~15 min]
Phase 4: Verify                                   [~10 min]

Phases 2 and 3 can run in parallel after Phase 1 completes.
```

---

## Deliverables Summary

| Artifact | Location | Type |
|:---------|:---------|:-----|
| Foundation repo | `C:\git\work\ibbytech-foundation\` | New repo |
| Foundation CLAUDE.md | `ibbytech-foundation\.claude\CLAUDE.md` | New |
| Rules 01-05 | `ibbytech-foundation\.claude\rules\` | Migrated/adapted |
| Skills (3) | `ibbytech-foundation\skills\` | Migrated |
| Templates (5) | `ibbytech-foundation\templates\` | Migrated + new |
| /start-session command | `~\.claude\commands\start-session.md` | New |
| Shogun CLAUDE.md | `C:\git\work\shogun\.claude\CLAUDE.md` | New |
| Shogun settings.json | `C:\git\work\shogun\.claude\settings.json` | New |
| Shogun planning-state | `C:\git\work\shogun\outputs\planning\planning-state.md` | New |
| Shogun validation dir | `C:\git\work\shogun\outputs\validation\.gitkeep` | New |
