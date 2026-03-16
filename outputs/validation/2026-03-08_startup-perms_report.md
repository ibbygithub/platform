# Session Startup Permission Fix — Evidence Report
Date: 2026-03-08
Outcome: COMPLETED

## Root Cause

The `*` wildcard in `settings.json` Bash allow patterns does NOT match compound
commands joined by `&&`. The pattern `"Bash(git status*)"` matches `git status`
but not `git status && echo "---" && git branch -a && ...`.

The previous fix attempt (`"Bash(git status && echo*)"`, commit `fc38aa0`) did
not resolve the issue — `*` still did not match the full continuation after `echo`.

## Changes Made

### `.claude/settings.json`
Added verbatim compound startup command as a literal allow entry:
```
"Bash(git status && echo \"---BRANCH---\" && git branch -a && echo \"---WORKTREE---\" && git worktree list && echo \"---LOG---\" && git log --oneline -5)"
```
This guarantees a match regardless of wildcard behavior.

### `.claude/CLAUDE.md` — Step 2
Added explicit note:
> Run each as a separate Bash call — do NOT combine with `&&`.
> Each command individually matches an allow pattern in `settings.json`.
> Compound `&&` chains bypass pattern matching and trigger permission prompts.

## Why Both Changes

- `settings.json` fix: covers the current compound command pattern agents naturally write
- `CLAUDE.md` fix: corrects future agent behavior — run 4 separate calls, each of which
  already has an individual matching pattern, eliminating the dependency on the verbatim entry
