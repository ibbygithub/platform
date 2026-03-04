# Safety Rules — Platform Guardrails

## Core Principle
Correctness and traceability are more important than speed or task completion.
When uncertain: stop, explain, ask. Never guess and proceed.

---

## Destructive Actions Require Confirmation

Before any destructive or irreversible action (dropping a table, removing a container,
deleting data, overwriting a file in production):

1. State what the action is and why it is necessary
2. Wait for explicit confirmation
3. Identify the rollback strategy

If there is no safe rollback — say so before proceeding, not after.

---

## Least Privilege — Always

Operate with the minimum access required for the task.

- Do not elevate privileges
- Do not reuse credentials across roles
- Do not use credentials discovered opportunistically
- If the assigned persona does not have sufficient access, stop and report — do not
  find another credential that does

---

## Evidence and Audit Logging

Every action that touches infrastructure must produce a persistent evidence artifact.

- Write evidence for every execution, including successful runs
- Capture raw command output where possible
- Default evidence path: `outputs/validation/YYYY-MM-DD_<task-name>_report.md`

Do not treat chat summaries as evidence.
Do not skip logging because no issues were found.
Silent actions are forbidden.

---

## Hard Block — Evidence Logging Requirement

If a deployment task completes without producing:
1. A service doc update in `.claude/services/`
2. An evidence record in `outputs/validation/`

The task is considered **incomplete**. Flag it, write the missing artifacts, then close.

---

## Error Handling

On any error or unexpected result:
1. Stop immediately
2. Capture the full error output
3. Write it to `outputs/validation/`
4. Report clearly — do not retry blindly

---

## Scope Control

Do not expand task scope without being asked.
Do not perform opportunistic actions ("while I'm here I'll also...").
Do not chain actions across nodes or domains without explicit instruction.

---

## Hard Block Violation — Output Format

When a HARD BLOCK is triggered, produce this exact output format in the session
and write the evidence record to `outputs/validation/`:

```
╔══════════════════════════════════════════════════════════════╗
║  🚫 HARD BLOCK — [VIOLATION TYPE]                           ║
╠══════════════════════════════════════════════════════════════╣
║  Task:      [What was requested]                            ║
║  Violation: [Exact rule being violated]                     ║
║  Source:    [Which rules file]                              ║
║  Guidance:  [Correct approach or node]                      ║
╚══════════════════════════════════════════════════════════════╝
```

Evidence file naming: `outputs/validation/YYYY-MM-DD_HARDBLOCK_<type>.md`

Hard block types:
- `CREDENTIAL_ESCALATION` — use of unauthorized SSH identity
- `CROSS_NODE_VIOLATION` — wrong workload on wrong node
- `TRANSPORT_BYPASS` — SCP/SFTP/rsync used instead of Git
