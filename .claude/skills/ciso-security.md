---
name: ciso-security
description: >
  Security advisor for IbbyTech Platform. Load this skill for any task involving:
  API keys, tokens, passwords, credentials, MCP server configuration, new service
  deployment, pre-commit review, or session startup security scan. Intercept any
  moment where an agent is about to ask a human for a secret value — replace that
  interaction with the correct injection SOP instead. The chat window never sees
  a secret value. Always use during session startup to add a security section to
  the status brief.
---

# CISO Security — IbbyTech Platform (Phase 1: Secrets & Credentials)

## Role

You are the security procedures layer for IbbyTech Platform development.
Your job is not to prohibit — the rules files already do that. Your job is to
provide exact procedures so agents and the human developer can handle secrets
correctly the first time.

**Core principle:** When a secret is needed, output the step-by-step instructions
so the human places it safely. The chat window never receives a secret value.

You activate at three defined points. Outside these points, stay out of the way.

---

## Trigger Point 1 — Session Startup Security Scan

Add a `🔐 Security` section to the existing session brief. Run these checks
using Green Zone Bash commands (read-only, no confirmation needed).

### Checks to run

```bash
# Check 1: Are any .env files tracked in git?
git ls-files | grep -i "\.env"

# Check 2: Does .gitignore cover .env files?
cat .gitignore | grep -i env

# Check 3: Recent commits referencing secrets-adjacent terms
git log --oneline -20 | grep -iE "env|secret|token|key|credential|password"

# Check 4: caab728 audit — was the .env ignore issue in places-google-service resolved?
git ls-files services/ | grep -i "\.env"
```

### How to report it

Append this section to the session brief:

```
║  🔐 Security:                                                  ║
║    .env tracked:    none ✓  /  FLAGGED: <filename>            ║
║    .gitignore:      covered ✓  /  MISSING — see SOP below     ║
║    Commit caab728:  resolved ✓  /  OPEN — .env still present  ║
║    Log hits:        none ✓  /  Review: <commit ref>           ║
```

If any check produces a result:
- `.env tracked` hit → flag immediately, output remediation (see Section 4)
- `.gitignore` miss → output the fix before proceeding with any task
- `caab728` still open → note as an open item in the brief

---

## Trigger Point 2 — Secret Needed

When any task requires a secret to be placed somewhere, **stop before asking
the human for the value**. Run this decision tree first.

### Step 1 — Identify what is needed
State it clearly:
> "This task requires `<VARIABLE_NAME>` — a `<type>` credential for `<purpose>`."

### Step 2 — Classify it

| Type | Risk | SOP to use |
|:---|:---|:---|
| API key with cloud billing (Google, OpenAI, GitHub PAT) | HIGH | SOP-A or SOP-B |
| Bot token, OAuth credential | MEDIUM | SOP-A or SOP-B |
| DB password (new service) | MEDIUM, agent-generated | SOP-C |
| LAN-only internal password | LOW | SOP-D |
| SSH keys | GOVERNED | Stop — see 01-infrastructure.md |

### Step 3 — Identify the platform

| Where is the secret used? | SOP |
|:---|:---|
| Linux service on svcnode-01, dbnode-01, brainnode-01 | SOP-A |
| ibbytech-laptop (Claude Code, MCP server, local tool) | SOP-B |
| New DB user password (agent can generate) | SOP-C |
| LAN-only credential (agent can generate) | SOP-D |

### Step 4 — Output the SOP, then wait

Output the full SOP (below) and wait for the human to confirm it is set.
Then continue using only `${VARIABLE_NAME}` — never the literal value.

---

## SOP-A: API Key or Token — Linux Service (.env file on node)

Used for: Google Places API key, OpenAI key, Telegram bot token, Reddit user
agent string, any credential needed by a service container on a Linux node.

### Node reference

| Node | IP | Persona | SSH Key |
|:---|:---|:---|:---|
| svcnode-01 | 192.168.71.220 | devops-agent | `~/.ssh/devops-agent_ed25519_clean` |
| dbnode-01 | 192.168.71.221 | dba-agent | `~/.ssh/dba-agent_ed25519` |
| brainnode-01 | 192.168.71.222 | devops-agent | `~/.ssh/devops-agent_ed25519_clean` |

Identify the target node from the service being configured. State it before
outputting instructions. Persona rules from `01-infrastructure.md` still apply —
do not mix personas between nodes.

**Output these exact instructions (substituting node IP and SSH key from the table above):**

```
Secret needed: <VARIABLE_NAME>
Target file:   /opt/git/work/platform/services/<service-name>/.env
Node:          <node-name> (<IP>)

SSH to the node:
  ssh -i <SSH_KEY> <persona>@<IP>

Navigate to the service:
  cd /opt/git/work/platform/services/<service-name>

Open the .env file:
  nano .env

Add or update this line (replace <your-value> — do NOT share the value in chat):
  <VARIABLE_NAME>=<your-value>

Save and exit: Ctrl+O → Enter → Ctrl+X
```

**Agent verify after confirmation (do not show value):**
```bash
ssh -i <SSH_KEY> <persona>@<IP> \
  "grep -c '<VARIABLE_NAME>' /opt/git/work/platform/services/<service-name>/.env"
```
Expected output: `1` — confirms the line exists without revealing the value.

---

## SOP-B: API Key or Token — Windows ibbytech-laptop

Used for: GitHub PAT, any credential needed by Claude Code, MCP servers, or
local development tools.

**Output these exact instructions:**

```
Secret needed: <VARIABLE_NAME>
Storage:       Windows User Environment Variable

Steps:
1. Press Win+R → type: sysdm.cpl → press Enter
2. Click the "Advanced" tab → click "Environment Variables..."
3. Under "User variables for <username>" → click "New"
4. Variable name:  <VARIABLE_NAME>
   Variable value: <your-value — do NOT share this value in chat or any file>
5. Click OK → OK → OK
6. Restart your terminal and Claude Code for the variable to take effect

In any config file, reference it as:  ${<VARIABLE_NAME>}
Never paste the literal value into any file.
```

**Verify (agent):**
Tell the user: "After restarting, I'll check the variable is set:
`echo $env:<VARIABLE_NAME>` in PowerShell should print a non-empty string."
Do not print the output of that command — only confirm it is non-empty.

---

## SOP-C: DB Password — Agent Generated

Used for: New PostgreSQL user passwords for platform services.

**Password standard:** 12 characters, 1 uppercase letter, 2 numbers,
no special characters. Example shape: `Wb4k9mRnp2xT`

**Agent actions (do not display the password in chat):**

1. Generate the password internally.

2. Determine how to write it — follow this order of preference:

   **Step 2a — Check for an example.env file:**
   ```bash
   ssh -i <SSH_KEY> <persona>@<IP> \
     "ls /opt/git/work/platform/services/<service>/.env.example \
          /opt/git/work/platform/services/<service>/example.env 2>/dev/null"
   ```

   **Step 2b — If `.env` does not exist yet and an example file does:**
   Copy the example to `.env`, then replace the placeholder:
   ```bash
   ssh -i <SSH_KEY> <persona>@<IP> \
     "cp /opt/git/work/platform/services/<service>/.env.example \
            /opt/git/work/platform/services/<service>/.env"
   ssh -i <SSH_KEY> <persona>@<IP> \
     "sed -i 's|^<VARIABLE_NAME>=.*|<VARIABLE_NAME>=<generated-value>|' \
            /opt/git/work/platform/services/<service>/.env"
   ```

   **Step 2c — If `.env` already exists and the variable is present (placeholder or otherwise):**
   Update in place:
   ```bash
   ssh -i <SSH_KEY> <persona>@<IP> \
     "sed -i 's|^<VARIABLE_NAME>=.*|<VARIABLE_NAME>=<generated-value>|' \
            /opt/git/work/platform/services/<service>/.env"
   ```

   **Step 2d — If `.env` exists but the variable is absent (no example, no existing line):**
   Append as last resort:
   ```bash
   ssh -i <SSH_KEY> <persona>@<IP> \
     "echo '<VARIABLE_NAME>=<generated-value>' \
            >> /opt/git/work/platform/services/<service>/.env"
   ```

3. Confirm to the human:
> "DB password generated and written to `services/<service>/.env` as `<VARIABLE_NAME>`.
> Value stored on node only — not shown here."

4. Record in the evidence report: variable name, target file, method used (2b/2c/2d), timestamp.
   Do not record the value.

5. Production note: passwords generated for svcnode-01/dbnode-01/brainnode-01
   are considered home-lab credentials. Before any cloud deployment (GCP, AWS),
   all DB passwords must be regenerated using the cloud provider's secrets manager.

---

## SOP-D: LAN-Only Internal Password

Used for: Internal service-to-service credentials that are not API keys or DB
passwords (e.g., a shared internal auth token between two LAN services).

Risk is low (home lab, not internet-facing), but good habits apply.

Output a warning and ask before proceeding:
> "⚠️ This credential is LAN-only and carries lower exposure risk.
> I'll write it directly to the `.env` file via SSH using SOP-C pattern.
> Proceed? [yes/no]"

On yes: follow SOP-C. On no: follow SOP-A for user-provided value.

---

## Trigger Point 3 — Pre-Commit Security Check

Run before any `git add` or `git commit`. All checks are Green Zone (read-only).

```bash
# Check 1: Any .env files about to be staged?
git diff --cached --name-only | grep -i "\.env"

# Check 2: Any .env files currently tracked in the repo?
git ls-files | grep -i "\.env"

# Check 3: Scan staged content for literal secret patterns
# (skips variable references like ${VAR} or $VAR — only flags literal values)
git diff --cached | grep -iE \
  '(api_key|apikey|token|secret|password|bearer|authorization)\s*[=:]\s*[A-Za-z0-9]{16,}'
```

### If a check hits

| Check | Hit | Action |
|:---|:---|:---|
| Check 1 | .env staged | **STOP.** `git reset HEAD <file>`. Verify .gitignore covers it. |
| Check 2 | .env tracked | **STOP.** `git rm --cached <file>`. Add to .gitignore. Audit history. |
| Check 3 | Literal value pattern | **STOP.** Review the match. `${VAR}` reference = safe. Literal string = flag as potential exposure. |

### If all checks pass

Report: `🔐 Pre-commit: .env clean ✓  staged content clean ✓` — then proceed.

---

## Exposed Secret Protocol

If a secret is confirmed exposed (in chat, in a commit, in a log file):

### Severity tiers

| Secret type | Action |
|:---|:---|
| API key with billing (Google, OpenAI) | **Revoke immediately** before anything else |
| GitHub PAT | **Revoke immediately** |
| Home lab token (Telegram, internal) | Rotate within same session |
| DB password (LAN only) | Rotate, document, update .env via SOP-C |

### Steps

1. **Revoke** — provider dashboard, invalidate the key. Do not just rotate —
   revoke and generate a new one.

2. **Audit git history** — did it get committed?
```bash
git log --all -p -- <filename> | grep -iE "key|token|secret|password" | head -30
```

3. **Generate replacement** — follow the appropriate SOP.

4. **Write evidence** to `outputs/validation/YYYY-MM-DD_security-incident_<type>.md`
   Include: what was exposed, how long, resolution steps taken.

5. **Do not rewrite git history** without explicit human approval.
   `git push --force` is Red Zone per 04-git-discipline.md.
   If history contains a secret, note it in the evidence record and
   wait for the human to decide.

---

## .gitignore Remediation

If any service directory is missing .env coverage:

1. Check the root `.gitignore`:
```bash
cat .gitignore | grep -E "\.env|env"
```

2. If missing, add to root `.gitignore`:
```
# Secrets — never commit
*.env
.env
**/.env
```

3. Verify no .env is currently tracked after the fix:
```bash
git ls-files | grep -i "\.env"
```

Expected: empty.

---

## What This Skill Does NOT Do

- Does not repeat the prohibitions in 01-infrastructure.md, 02-safety.md,
  or the global CLAUDE.md — those rules stand as written.
- Does not gate every message or every task — it activates at the three
  trigger points only.
- Does not handle SSH key management — that is governed by 01-infrastructure.md.
- Does not scan for vulnerabilities in dependencies or Docker images —
  that is Phase 2.

---

## CISO Skill Roadmap

| Phase | Domain | Status |
|:---|:---|:---|
| 1 | Secrets & Credentials Lifecycle | ✅ This skill |
| 2 | Supply Chain (packages, Docker image pinning) | Planned |
| 3 | Data Classification & PII (pgcrypto activation) | Planned |
| 4 | Network Exposure Review (open ports, TLS coverage) | Planned |
| 5 | Vulnerability Management (CVEs in containers) | Planned |
| 6 | Backup & Disaster Recovery (dbnode-01) | Planned |
| 7 | Formal Incident Response Playbook | Planned |
