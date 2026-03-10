# Evidence Report — Settings Approval Fix

**Date:** 2026-03-10
**Branch:** feature/20260310-settings-approval-fix
**Outcome:** Completed

---

## Problem

Two issues causing unnecessary approval prompts:

1. `git ls-files` was not in `settings.json` allow list. The CISO security scan
   (Step 2.5) runs `git ls-files | grep -i "\.env"` twice. Despite CLAUDE.md
   labeling these "Green Zone — no confirmation needed", they would prompt for
   approval every session.

2. Step 2 note in CLAUDE.md contained inaccurate guidance: "do NOT combine with
   `&&` — compound chains bypass pattern matching". This was written before the
   `cd C:/git/work/platform && git ...` patterns were added to settings.json
   (lines 93–106). The note caused unnecessary workarounds and was misleading.

---

## Changes Made

### `.claude/settings.json`
- Added `"Bash(git ls-files*)"` to the allow list (after `git worktree list*`)
- No patterns removed. No deny list changes.

### `.claude/CLAUDE.md`
- Updated Step 2 note from:
  > "do NOT combine with `&&`. Compound `&&` chains bypass pattern matching"
- To:
  > "Avoid multi-command `&&` chains unless a matching combined pattern exists
  > in `settings.json`."
- Accurately reflects that `cd C:/git/work/platform && git ...` patterns
  already exist and do not require approval.

---

## Verification

The 4 historical examples that triggered approvals all match existing patterns:
| Command | Pattern |
|:---|:---|
| `cd C:/git/work/platform && git log --oneline -3` | `Bash(cd C:/git/work/platform && git log*)` |
| `cd C:/git/work/platform && git add ...` | `Bash(cd C:/git/work/platform && git add*)` |
| `cd C:/git/work/platform && git diff --cached --stat` | `Bash(cd C:/git/work/platform && git diff*)` |
| `cd C:/git/work/platform && git commit -m "..."` | `Bash(cd C:/git/work/platform && git commit*)` |

Security scan commands now fully covered:
| Command | Pattern |
|:---|:---|
| `git ls-files \| grep -i "\.env"` | `Bash(git ls-files*)` ← **added** |
| `cat .gitignore \| grep -i env` | `Bash(cat *)` |
| `git log --oneline -20 \| grep -iE "..."` | `Bash(git log *)` |
| `git ls-files services/ \| grep -i "\.env"` | `Bash(git ls-files*)` ← **added** |
