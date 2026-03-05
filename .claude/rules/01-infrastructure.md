# Infrastructure Rules — Node Roles & Identity

## Node Role Enforcement

### svcnode-01 (192.168.71.220)
- Runs: Docker containers, Traefik reverse proxy, all API gateways and enterprise services
- Does NOT: store persistent data, host application logic, run cron jobs
- Persona required: `devops-agent`
- If a task asks you to store database data on svcnode-01 → HARD BLOCK (cross-node violation)

### dbnode-01 (192.168.71.221)
- Runs: PostgreSQL `shogun_v1` exclusively
- Does NOT: run Docker, host applications, serve APIs
- Persona required: `dba-agent`
- If a task asks you to run Docker on dbnode-01 → HARD BLOCK (cross-node violation)
- If a task asks you to deploy an application to dbnode-01 → HARD BLOCK (cross-node violation)

### brainnode-01 (192.168.71.222)
- Runs: Main applications, MCP servers, cron jobs, ETL scripts, Python automation
- Does NOT: run Docker, host databases
- Persona required: `devops-agent`
- If a task asks you to run Docker on brainnode-01 → HARD BLOCK (cross-node violation)

### ibbytech-laptop (Windows 11 — Control Plane)
- Runs: All code editing, Git operations, PowerShell, SSH session initiation
- Does NOT: run production workloads, host services, execute deployment logic
- If a task asks you to run a production workload on the laptop → redirect to correct node

---

## Persona Assignment Rules

Before any task involving remote node access, explicitly identify the required persona.

State it once, briefly:
> "Task targets svcnode-01 — using devops-agent."

Do not combine personas within a single task.
Do not switch personas mid-task without stating the reason.

### SSH Identity Constraints (Hard Block Triggers)
- Use ONLY the identity file mapped to the active persona
- `devops-agent` → `~/.ssh/devops-agent_ed25519_clean` only
- `dba-agent` → `~/.ssh/dba-agent_ed25519` only
- **Never use any other SSH key found in `~/.ssh/` or elsewhere on the system**
- Discovering an alternative credential and using it to bypass a permission error
  is credential escalation — this triggers an immediate HARD BLOCK and evidence log

---

## Transport Rules

- Code moves from laptop to nodes via **Git push/pull only**
- SCP, SFTP, rsync, and direct file copy are forbidden transport methods
- If a task suggests using SCP or SFTP → HARD BLOCK (transport bypass violation)

---

## DNS Fallback

Internal DNS: `*.ibbytech.com` and `*.platform.ibbytech.com`
If DNS resolution fails, fall back to direct IP:
- svcnode-01: `192.168.71.220`
- dbnode-01: `192.168.71.221`
- brainnode-01: `192.168.71.222`

All nodes are on the `192.168.71.x` internal network only. No public exposure.

---

## Path Convention Exceptions

The platform path standard for Linux nodes is `/opt/git/work/<project-name>/`.
The following services are exempt by documented decision — do not treat their
paths as a pattern to follow.

| Service | Actual Path | Node | Exception Reason |
|:---|:---|:---|:---|
| Firecrawl | `/opt/firecrawl` | svcnode-01 | Installed via upstream Docker Compose repo before path standard was codified. Root-owned `.env`. Migration risk exceeds benefit. Exception approved 2026-03-05. |

**All new services must comply with the standard path.** This list is for
legacy services only and will not grow without explicit sign-off.
