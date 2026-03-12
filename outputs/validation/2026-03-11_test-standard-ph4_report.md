# Evidence Report — Platform Test Standard Phase 4

**Date:** 2026-03-11
**Branch:** feature/20260311-test-standard-ph4
**Task:** Bake Platform Test Standard into CLAUDE.md and platform rules permanently

---

## Objective

Phase 4 of the Platform Test Standard: embed the delivery checklist and development
cycle requirements into the platform's governing rules files so every future build
task inherits the standard automatically without relying on a developer knowing the
plan document.

---

## Changes Made

### 1. `.claude/CLAUDE.md` — Stage 3 Delivery Gate added

Inserted a new `## Stage 3 — Delivery Gate (Green Gate Checklist)` section between
Stage 2 (Execution Plan Approval) and Scope Discipline During Execution.

**What it contains:**
- 7-item Green Gate checklist table with verify instructions
- Exemption rules (non-service tasks, existing services with no functional change,
  known Loki gaps as WARN not FAIL)
- Delivery Gate output format (structured box, parallel to Stage 2 Execution Plan format)
- Rule: any unresolved FAIL blocks merge; WARN items may proceed if documented

**Why:** The CLAUDE.md previously had Stage 2 (approval before work) but no
corresponding delivery gate after work. A developer completing a service task had
no rules-level checklist to verify against. This closes that gap.

### 2. `.claude/rules/03-platform-standards.md` — Service Documentation section expanded

Replaced the 4-line "produce a service doc" section with a full mandatory artifacts
table and detailed requirements for validate scripts and OpenAPI specs.

**What it contains:**
- Artifacts table: service doc, OpenAPI spec, validate script, _index.md, .env.example
- Validate script requirements: 7-step structure, shared fixtures, Loki helper, Green Gate output
- OpenAPI spec requirements: 3.1.0 format, server entries, receive-only service pattern
- References to reference implementations (scraper, reddit-gateway)
- Cross-reference to CLAUDE.md Stage 3 for final verification

**Why:** The old section only required a service doc. Nothing required validate scripts
or OpenAPI specs, meaning new services could be deployed without the testing infrastructure
the Test Standard established in Phases 1–3.

### 3. `templates/service-doc-template.md` — Created

New file. Complete service doc template with all required sections including:
- `## Capabilities` table with status definitions and Last Updated field
- `.env.example` placeholder format
- Python consumption example
- Rate limiting and known limitations sections
- Observability section with Loki label

**Why:** `03-platform-standards.md` references this template but it did not exist.
Every future service doc now has a single authoritative starting point.

### 4. `outputs/planning/planning-state.md` — Platform Test Standard marked complete

Updated Active Work table and Planning Documents table to reflect all 4 phases complete.

---

## Green Gate Checklist

| # | Item | Status |
|:--|:-----|:-------|
| 1 | Validate PASS | SKIP — no service deployed, rules/docs only |
| 2 | Loki Level 1 | SKIP — no service deployed |
| 3 | OpenAPI spec | SKIP — no service deployed |
| 4 | Capability registry | SKIP — no service deployed |
| 5 | _index.md | SKIP — no service entry changed |
| 6 | Evidence report | PASS — this file |
| 7 | .env.example | SKIP — no new env vars |

---

## Phase Summary — Platform Test Standard Complete

All 4 phases of the Platform Test Standard have been delivered:

| Phase | Description | Date | Status |
|:------|:------------|:-----|:-------|
| Phase 1 | Test harness foundation: platform_preflight.py, shared fixtures, Loki helper | 2026-03-11 | Complete |
| Phase 2 | Reference implementation: scraper validate script + OpenAPI spec | 2026-03-11 | Complete |
| Phase 3 | Apply standard to 4 remaining services: Reddit, Telegram, Places, LLM | 2026-03-11 | Complete |
| Phase 4 | Bake delivery checklist into CLAUDE.md and rules — permanent enforcement | 2026-03-11 | Complete |

The platform development cycle is now formally governed by 5 stages:
1. Session Startup (CLAUDE.md startup protocol)
2. Task Onboarding — Part A preflight + Part B capability pre-check (CLAUDE.md Step 2.5)
3. Build (03-platform-standards.md — API-first, all artifacts required)
4. Post-Deployment Validation (validate scripts, Green Gate)
5. Delivery Gate (CLAUDE.md Stage 3 — 7-item checklist, box format, blocks merge on FAIL)

---

## Outcome

**COMPLETE.** Platform Test Standard fully embedded in governing rules.
No external planning document is required to know the delivery standard.
Every new session reads CLAUDE.md and 03-platform-standards.md at startup —
the standard is now ambient, not advisory.
