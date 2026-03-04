# Command: /register-service

## Purpose
Register a new or recently deployed service on svcnode-01 by generating a
complete service doc and updating the platform service index.

Run this command after any new service is deployed to svcnode-01.

---

## What This Command Does

1. Prompts for the service details listed below
2. Generates a populated service doc using `templates/service-doc-template.md`
3. Saves the doc to `.claude/services/<service-name>.md`
4. Updates `.claude/services/_index.md` with the new entry
5. Writes an evidence record to `outputs/validation/`

---

## Required Inputs

When invoked, ask the user for:

1. **Service name** — short slug (e.g., `firecrawl`, `reddit-api`)
2. **FQDN** — the public-facing endpoint (e.g., `scrape.platform.ibbytech.com`)
3. **Auth method** — Bearer Token / API Key / Bot Token / None
4. **Env variable name** — the `.env` key that holds the credential
5. **What the service does** — one sentence
6. **Known limitations or quirks** — anything an agent needs to know before using it
7. **Loki label** — the `service=` label used in log output (or "not yet configured")
8. **Grafana dashboard** — URL or "not yet configured"
9. **Status** — Active / Degraded / Planned

---

## Output

Creates: `.claude/services/<service-name>.md`
Updates: `.claude/services/_index.md`
Evidence: `outputs/validation/YYYY-MM-DD_register-service_<name>.md`

---

## Usage

```
/register-service
```

No arguments needed — the command will prompt for each required field.
