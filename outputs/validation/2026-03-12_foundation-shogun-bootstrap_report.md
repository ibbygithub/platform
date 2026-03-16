# Evidence Report — IbbyTech Foundation + Shogun Bootstrap

**Date:** 2026-03-12
**Branch:** develop (platform planning/docs work — no feature branch needed)
**Task:** Create ibbytech-foundation repo, /start-session command, scaffold Shogun
**Node(s):** laptop only
**Persona(s):** none (all laptop-side file creation and git operations)

---

## Objective

Establish `ibbytech-foundation` as the single source of truth for Claude Code
engineering rules, skills, and templates across all IbbyTech projects. Scaffold
Shogun as the first consumer. Establish `/start-session` as a universal startup
command available in every project session on this machine.

---

## Actions Taken

### Phase 0 — ibbytech-foundation repo created

Created `C:\git\work\ibbytech-foundation\` with folder structure:
- `.claude/` — foundation CLAUDE.md and rules/
- `skills/` — CISO, dbnode-01 skills
- `templates/` — service-doc, evidence-report, openapi, project-claude-md, settings-baseline

Git initialized, initial commit `4449986`, pushed to:
`https://github.com/ibbygithub/ibbytech-foundation.git` (private repo — already existed)

### Phase 1 — Foundation populated

Files created:

| File | Source | Notes |
|:-----|:-------|:------|
| `.claude/CLAUDE.md` | New | Behavioral rules: two-stage approval, green gate, autonomy, communication standards |
| `.claude/rules/01-infrastructure.md` | Copied from platform | No changes — homelab-wide content |
| `.claude/rules/02-safety.md` | Copied from platform | No changes |
| `.claude/rules/03-platform-standards.md` | Adapted from platform | 3 changes: services index path, templates path, foundation reference section |
| `.claude/rules/04-git-discipline.md` | Adapted from platform | "platform repo" → "all projects" in branch architecture heading |
| `.claude/rules/05-database.md` | Copied from platform | Reference Files section generalized to project-local path |
| `skills/ciso-security.md` | Copied from platform | No changes |
| `skills/dbnode-01-skill.md` | Copied from platform | No changes |
| `templates/service-doc-template.md` | Copied from platform | No changes |
| `templates/evidence-report-template.md` | New | Standard evidence report skeleton |
| `templates/openapi-template.yaml` | New | OpenAPI 3.1.0 skeleton with standard structure |
| `templates/project-claude-md-template.md` | New | Template for new project CLAUDE.md files |
| `templates/settings-baseline.json` | Copied from platform | Full allow/deny baseline |

### Phase 2 — /start-session command created

Location: `C:\Users\toddi\.claude\commands\start-session.md`

Command executes 8 steps: load foundation rules → CISO Trigger Point 1 security
scan → git state check → conditional preflight → last work context → planning
state read → session brief → "What are we working on today?"

Available in every Claude Code session on this machine without any per-project
setup or `--add-dir`.

### Phase 3 — Shogun scaffolded

Pre-check: Shogun was on `feature/gateway-pure-search-endpoints`, 2 commits
ahead of origin, with a modified `outputs/planning/planning-state.md`. This
matched known state. Proceeded.

Discovery: Shogun's `.gitignore` excluded `.claude/` entirely. Fixed by
replacing directory-level ignore with specific ignores for `worktrees/` and
`settings.local.json`, allowing `CLAUDE.md` and `settings.json` to be tracked.

Discovery: Shogun already had a rich `planning-state.md` (last updated 2026-03-10)
with Valkey, DNS, and shogun-core decisions. Merged rather than overwrote:
added foundation bootstrap to Active Work, added Google Places routing decision
to Decision Log, updated date to 2026-03-12.

Files created/modified in Shogun:

| File | Action |
|:-----|:-------|
| `.claude/CLAUDE.md` | Created — Shogun project identity, nodes, platform services, database routing, known state, open decisions, tech registry |
| `.claude/settings.json` | Created — settings-baseline.json with platform paths changed to shogun paths |
| `.gitignore` | Modified — allow .claude/CLAUDE.md and .claude/settings.json to be tracked |
| `outputs/planning/planning-state.md` | Updated — bootstrap added, Places decision added, date updated |
| `outputs/validation/.gitkeep` | Created — establishes validation directory |

Commit: `4ce5f22` on `feature/gateway-pure-search-endpoints`.

---

## Verification

```
ibbytech-foundation/
├── .claude/
│   ├── CLAUDE.md                    ✓
│   └── rules/
│       ├── 01-infrastructure.md     ✓
│       ├── 02-safety.md             ✓
│       ├── 03-platform-standards.md ✓ (adapted)
│       ├── 04-git-discipline.md     ✓ (adapted)
│       └── 05-database.md           ✓
├── .gitignore                       ✓
├── skills/
│   ├── ciso-security.md             ✓
│   └── dbnode-01-skill.md           ✓
└── templates/
    ├── evidence-report-template.md  ✓
    ├── openapi-template.yaml        ✓
    ├── project-claude-md-template.md ✓
    ├── service-doc-template.md      ✓
    └── settings-baseline.json       ✓

~/.claude/commands/start-session.md  ✓

C:\git\work\shogun\
├── .claude/
│   ├── CLAUDE.md                    ✓
│   └── settings.json                ✓
├── outputs/
│   ├── planning/planning-state.md   ✓ (updated)
│   └── validation/.gitkeep          ✓
└── .gitignore                       ✓ (updated)
```

GitHub: `https://github.com/ibbygithub/ibbytech-foundation.git` — pushed ✓

---

## Green Gate Checklist

| # | Item | Status |
|:--|:-----|:-------|
| 1 | Validate PASS | SKIP — no platform service deployed |
| 2 | Loki Level 1 | SKIP |
| 3 | OpenAPI spec | SKIP |
| 4 | Capability registry | SKIP |
| 5 | _index.md | SKIP |
| 6 | Evidence report | PASS — this file |
| 7 | .env.example | SKIP — no new env vars |

---

## Open Items (Post-Task Follow-Up)

1. **Platform refactor:** Update platform CLAUDE.md to use `/start-session`
   and reference foundation rules instead of maintaining its own copies.
   Prevents drift as platform rules evolve.

2. **New-project scaffolder command:** A `/new-project` command that automates
   the Shogun scaffold steps for future projects. Template established —
   extract into command after second project is bootstrapped.

3. **Shogun deploy branch:** `feature/gateway-pure-search-endpoints` on
   svcnode-01 still has 2 unmerged commits. Requires resolution before
   next Shogun deployment.

---

## Outcome

**COMPLETE.** Foundation established and pushed to GitHub. `/start-session`
available user-wide. Shogun scaffolded and committed. Starting Claude in Shogun
with `claude --add-dir ../ibbytech-foundation` and running `/start-session`
will produce the full session brief with security scan, git state, planning
state, and all foundation rules loaded.
