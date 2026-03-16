# Evidence Report — CISO Security Skill (Phase 1)

**Date:** 2026-03-10
**Task:** Create CISO security skill for IbbyTech Platform
**Outcome:** Completed

---

## What Was Built

### New file: `.claude/skills/ciso-security.md`

A procedures-first security skill covering Phase 1: Secrets & Credentials Lifecycle.

**Three trigger points:**
1. Session startup — security scan + section added to session brief
2. Secret needed — intercept and output exact SOP before chat sees any value
3. Pre-commit — pattern scan on staged files

**SOPs defined:**
| SOP | Used for |
|:---|:---|
| SOP-A | API key / token → Linux service `.env` via nano |
| SOP-B | API key / token → Windows sysdm.cpl → env var |
| SOP-C | DB password → agent-generated (12c, 1 upper, 2 num, no special), written via SSH |
| SOP-D | LAN-only internal credential → warning + proceed |

**Password generation standard:** 12 characters, 1 uppercase, 2 numbers, no special characters.

**Production boundary defined:** svcnode-01, dbnode-01, brainnode-01 = home lab.
GCP/AWS = production → all secrets must be regenerated using cloud provider secrets manager.

### Modified: `.claude/CLAUDE.md`

- Added **Step 2.5 — Security Scan** to the mandatory session startup protocol
- Added **`🔐 Security` row** to the Session Brief template

### Incident context

This skill was built in response to a GitHub PAT circular exposure incident where:
- A token was pasted into chat to configure an MCP server
- The token ended up hardcoded in `~/.claude.json`
- The cycle repeated twice before the root cause was identified
- Root cause: no documented procedure for secret injection — only a prohibition

The skill addresses the root cause by providing procedures, not adding prohibitions.

---

## Open Items Carried Forward

- `caab728` — `.env ignore issues` in places-google-service: **unreviewed**, flagged
  for audit in the security scan check at every session start.

---

## CISO Roadmap — Phases Planned

| Phase | Domain |
|:---|:---|
| 2 | Supply Chain Security |
| 3 | Data Classification & PII |
| 4 | Network Exposure Review |
| 5 | Vulnerability Management |
| 6 | Backup & Disaster Recovery |
| 7 | Formal Incident Response Playbook |
