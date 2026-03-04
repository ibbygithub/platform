# Platform Standards — Engineering Decisions

## Enterprise Services First (Consume, Don't Build)

Before implementing any new capability, check `.claude/services/_index.md`.

If the capability already exists as a platform service on `svcnode-01`:
- Use the existing gateway
- Do not create a duplicate service, container, or API wrapper
- Reference the service doc for endpoint, auth, and consumption pattern

Examples of what this means in practice:
- Need web scraping? → Use Firecrawl gateway. Do not install BeautifulSoup and
  scrape directly.
- Need to send a Telegram message? → Use Telegram Bot gateway. Do not create a
  new bot token or direct API integration.
- Need an LLM completion? → Use LLM Gateway. Do not hardcode a direct API call
  to OpenAI/Anthropic/etc.
- Need place data? → Use Google Places gateway. Do not use the raw Google Places
  API directly.

If a needed service does not exist yet, say so and propose it as a new platform
service before building it inline.

---

## Service Documentation — Mandatory Deployment Artifact

Every deployment task that creates or modifies a service on `svcnode-01` must
produce or update a service doc in `.claude/services/` before the task is
considered complete.

Use `templates/service-doc-template.md` as the base.
Update `_index.md` to reflect any new or changed service.

A deployment without a service doc update is an incomplete task.

---

## Observability Requirements

Every service must:
- Emit structured logs to Loki with a consistent `service=` label
- Log all inbound requests and outbound API calls
- Include response codes, latency, and error details in log output

If you write a service that does not meet this standard, mark it explicitly:
> "⚠️ Observability incomplete — Loki logging not yet implemented."

Do not silently ship a service with no logging.

---

## Environment Variables and Secrets

- Reference secrets by environment variable name only (e.g., `PLACES_API_KEY`)
- Never hardcode API keys, tokens, or passwords in code
- `.env` files live at the project root on the laptop and are injected by
  Docker Compose on deployment — do not replicate or copy `.env` contents
- If a required env variable is missing from `.env`, stop and report it —
  do not substitute a hardcoded value

---

## Project Path Standard

| Environment | Path Pattern |
|:---|:---|
| Windows (laptop) | `C:\git\work\<project-name>\` |
| Linux nodes | `/opt/git/work/<project-name>/` |

All projects follow this convention. Do not use ad-hoc paths.

---

## Referencing This Platform Repo From Other Projects

In any project's `CLAUDE.md`, include:

```
## Platform Reference
Infrastructure standards and service docs: ../platform
Use: claude --add-dir ../platform
```

This gives Claude Code sessions in that project full access to the platform
service index and rules without duplicating content.
