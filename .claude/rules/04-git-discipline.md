# Git Discipline — Branch Strategy, Worktree Policy, and Agent Lifecycle

## Core Principle

Git operations are infrastructure operations. They carry the same discipline
requirements as node access, service deployment, and credential use.
Correctness and traceability are not optional. Speed is never a justification
for skipping the lifecycle contract defined here.

---

## Branch Architecture

The platform repo uses a three-tier branch model.

| Branch | Purpose | Who Writes | Who Merges |
|:---|:---|:---|:---|
| `main` | Production-canonical state | Nobody directly | Human confirm only |
| `develop` | Integration — all features land here first | Agent (via merge) | Agent with Yellow confirm |
| `feature/<YYYYMMDD>-<task-slug>` | Active agent work | Agent | Agent proposes → Yellow confirm |
| `hotfix/<YYYYMMDD>-<issue-slug>` | Urgent targeted fixes | Agent | Agent proposes → Yellow confirm |

### Rules

- `main` is never committed to directly. By anyone. Ever.
- `develop` is the merge target for all completed feature and hotfix branches.
- `develop` → `main` promotion requires explicit human instruction. The agent
  does not initiate this without being asked.
- If a task does not clearly map to an existing branch, create a new
  `feature/` branch. Do not work on `develop` directly.

---

## Branch Naming Convention

Branch names are constructed by the agent using this exact format:

```
feature/YYYYMMDD-<task-slug>
hotfix/YYYYMMDD-<issue-slug>
```

### Rules

- `YYYYMMDD` is the date the branch is created (today's date at creation time)
- `<task-slug>` is a short, lowercase, hyphen-separated description of the task
- Slugs must be meaningful and traceable to the task being performed
- Random words, session IDs, and auto-generated strings are forbidden
- Maximum slug length: 40 characters

### Valid examples

```
feature/20260305-firecrawl-postgres-validation
feature/20260305-reddit-gateway-service-doc
feature/20260305-llm-gate-loki-logging
hotfix/20260305-traefik-label-correction
```

### Invalid examples

```
witty-platypus          ← random words — HARD BLOCK
claude-session-3        ← session artifact — HARD BLOCK
fix                     ← no date, no context — HARD BLOCK
feature/my-changes      ← no date — HARD BLOCK
```

---

## Worktree Policy

Worktrees are permitted for parallel task isolation. They are governed by a
strict lifecycle contract. Unmanaged worktrees are platform rot.

### Creation Rules

- One worktree per feature branch. One feature branch per discrete task.
- The worktree directory name **must match the branch name exactly**
- Worktrees are created under `.claude/worktrees/<branch-name>/`
- Before creating a worktree, state the task it represents and the branch
  name it will use

### Lifecycle Contract

Every worktree follows one of two exit paths. There is no third option.

**Path A — Task Completed Successfully:**
1. Agent runs validation and captures evidence
2. Agent presents Merge Ready notice (see format below)
3. Human responds `proceed` or `hold`
4. On `proceed`: agent merges to `develop` using `--no-ff`, deletes worktree,
   deletes local feature branch
5. Agent writes evidence record to `outputs/validation/`

**Path B — Task Abandoned or Superseded:**
1. Agent states reason for abandonment
2. Agent explicitly deletes the worktree directory
3. Agent deletes the local feature branch
4. Agent writes abandonment record to `outputs/validation/`

### Hard Block Triggers

- Worktree directory name does not match branch name → HARD BLOCK
- Worktree exists after task completion without Path A or Path B executed → HARD BLOCK
- More than 3 active worktrees simultaneously without explicit human approval → HARD BLOCK

---

## Commit Standards

### Commit Message Format

```
<type>(<scope>): <short description>

<optional body — what and why, not how>
```

| Type | Use for |
|:---|:---|
| `feat` | New capability or service |
| `fix` | Bug or configuration correction |
| `docs` | Documentation only changes |
| `chore` | Maintenance, dependency updates, cleanup |
| `deploy` | Deployment configuration changes |
| `security` | Security-related changes |

### Rules

- Commit messages must be meaningful. "fix", "update", "changes" are forbidden.
- Commit early and often within a feature branch — do not accumulate large
  uncommitted diffs
- Never commit secrets, `.env` files, or credential material — if this is
  detected, stop immediately and report
- Every commit on a feature branch must leave the branch in a runnable state

### Valid examples

```
feat(firecrawl): add postgres persistence with pgvector support
fix(traefik): correct service label for llm-gateway routing
docs(reddit-gateway): add service doc and register in _index.md
security(ssh): rotate devops-agent key reference in compose config
```

---

## Operation Zone Classification

Git operations are classified into three zones. Zone determines agent autonomy.

### Green Zone — Agent Acts Autonomously

No confirmation required. These operations are local, reversible, and
carry no risk to shared state.

- `git status`, `git log`, `git diff`, `git show`
- `git branch` (create local feature branch)
- `git checkout`, `git switch`
- `git add`, `git commit`
- `git stash`, `git stash pop`
- `git worktree add` (with compliant naming)
- `git fetch` (read-only remote sync)

### Yellow Zone — Agent Proposes, Human Confirms

Agent prepares the operation, presents the Merge Ready notice, and waits.
Human responds `proceed` or `hold`. No timeout — agent waits indefinitely.

- `git merge` (feature → develop)
- `git push` (any branch to remote)
- `git worktree remove`
- `git branch -d` (delete local branch post-merge)
- `git tag`
- `git rebase` (only on unshared branches)

### Red Zone — Human Only

Agent stops, explains what is needed and why, and hands off completely.
Agent does not execute these under any circumstances.

- `git push --force` or `git push --force-with-lease`
- `git reset --hard`
- `git clean -fd`
- `git branch -D` (force delete)
- Any operation on `main` branch directly
- `git remote set-url` or any remote configuration change
- Deletion of remote branches

---

## Merge Ready Notice — Required Format

When a task reaches Yellow Zone merge readiness, the agent must produce
this exact format before any merge or push operation:

```
╔══════════════════════════════════════════════════════════════════╗
║  ⏸  MERGE READY — Human Verification Required                  ║
╠══════════════════════════════════════════════════════════════════╣
║  Branch:     feature/YYYYMMDD-task-slug                        ║
║  Target:     develop                                            ║
║  Commits:    N commits since branch creation                    ║
║  Files:      N modified, N added, N deleted                     ║
║  Validated:  [brief description of what was tested/verified]   ║
║  Evidence:   outputs/validation/YYYY-MM-DD_<task>_report.md    ║
╚══════════════════════════════════════════════════════════════════╝

Changes summary:
- [plain English description of what changed and why]
- [any known risks or dependencies]

Respond "proceed" to merge to develop, or "hold" to pause.
```

The agent does not proceed until receiving an explicit `proceed` response.
`ok`, `yes`, `do it`, `go ahead` are all accepted as equivalent to `proceed`.
Silence is not consent. Ambiguous responses prompt the agent to re-ask once.

---

## Parallel Task Rules

When two or more worktrees are active simultaneously:

- Each task must have a declared scope at creation time (which files/services
  it will touch)
- No two parallel tasks may modify the same file without a declared dependency
  logged in both task briefs
- If a conflict is detected during merge, stop both tasks, report the conflict,
  and wait for human resolution guidance
- Parallel tasks are merged to `develop` sequentially, not simultaneously
- The second merge must include a `git pull develop` before merge to incorporate
  the first task's changes

---

## Session Startup — Git State Check

At the start of every session, before any task work begins, the agent must:

1. Run `git status` and report current branch and any uncommitted changes
2. Run `git branch -a` and report any feature branches older than 7 days
3. Run `git worktree list` and report any worktrees present
4. If stale branches or orphaned worktrees are found — flag them and ask
   whether to clean up before proceeding

This takes under 10 seconds and prevents sessions from starting on a
corrupted or ambiguous git state.

---

## Hard Block — Git Violation Output Format

When a git-related HARD BLOCK is triggered, use the standard format from
`02-safety.md` with these git-specific violation types:

- `GIT_FORBIDDEN_OPERATION` — Red Zone operation attempted
- `GIT_NAMING_VIOLATION` — branch or worktree name does not comply
- `GIT_MAIN_DIRECT_WRITE` — any attempt to commit or push directly to main
- `GIT_WORKTREE_ROT` — worktree exists beyond task lifecycle without cleanup
- `GIT_PARALLEL_CONFLICT` — two active tasks declared overlapping file scope
- `GIT_UNAUTHORIZED_PUSH` — push attempted without Yellow Zone confirmation

Evidence file naming: `outputs/validation/YYYY-MM-DD_HARDBLOCK_GIT_<type>.md`
