# Playwright Agent Workflow — IbbyTech Platform

## Purpose

Documents how Claude Code agent sessions use the Playwright MCP server to
visually verify deployed web interfaces. This is an agent-driven workflow
executed during Stage 4 (Post-Deployment Validation) when a task deliverable
includes a web UI.

This guide covers the **agent workflow** (session-time, human + agent together).
Automated Playwright test scripts that run independently are a separate
deliverable — see Future Actions in the Platform Test Standard plan.

---

## When This Workflow Applies

Use the Playwright agent workflow whenever a task deploys or modifies:
- A web frontend (dashboard, Shogun UI, admin page)
- A service that renders HTML responses
- Any URL that should be visually verified as part of post-deployment validation

Does NOT apply to pure API services (no UI) — use the validate_*.py script instead.

---

## MCP Server Setup

The Playwright MCP server is registered globally in `~/.claude.json` under
`mcpServers.playwright`. It was installed in MCP Env 1 (2026-03-09).

Package: `@playwright/mcp@latest`
Transport: stdio (npx on demand — no persistent server process)
Scope: user (all Claude Code sessions on ibbytech-laptop)

Verify it is active in any session:
```
/mcp  →  should list "playwright" under active MCP servers
```

---

## Standard Verification Workflow

Execute these steps in sequence when a web UI needs agent-driven verification.

### Step 1 — Navigate to the deployed URL

```
mcp__playwright__browser_navigate
  url: "http://{deployed-service-url}"
```

Use the internal platform URL (e.g., `http://shogun.platform.ibbytech.com`)
or `http://localhost:{port}` for laptop-local services.

### Step 2 — Capture initial page state

```
mcp__playwright__browser_snapshot
```

This returns the page's accessibility tree — text content, roles, and
interactive elements. Read the snapshot to confirm:
- Page title is correct
- Key UI elements are present (nav, headings, main content area)
- No error messages visible ("500 Internal Server Error", "Cannot connect", etc.)

### Step 3 — Take a screenshot for evidence

```
mcp__playwright__browser_take_screenshot
```

Save the screenshot path. It will be referenced in the evidence report.
Screenshot serves as the visual evidence artifact for the delivery checklist.

### Step 4 — Exercise interactive features

For each key user interaction the UI supports, verify it works:

**Navigation / page routing:**
```
mcp__playwright__browser_click
  element: "nav link or button description"
```
After click: run `browser_snapshot` again to confirm page changed as expected.

**Form submission:**
```
mcp__playwright__browser_fill_form
  fields: {"field-label": "test value", ...}
```
Follow with `browser_snapshot` to confirm form response.

**Dynamic content loading (API-backed UI):**
```
mcp__playwright__browser_wait_for
  text: "expected content that loads asynchronously"
```
Then `browser_snapshot` to confirm content appeared.

### Step 5 — Check browser console for errors

```
mcp__playwright__browser_console_messages
```

Review for:
- JavaScript errors (red error entries)
- Failed network requests (404s, 500s from API calls)
- Unexpected warnings that indicate broken functionality

### Step 6 — Capture final screenshot

```
mcp__playwright__browser_take_screenshot
```

Capture the final verified state. Include in evidence report.

### Step 7 — Close the browser

```
mcp__playwright__browser_close
```

Always close the browser at end of verification. Playwright MCP holds a
browser instance open until explicitly closed or the session ends.

---

## Evidence Report Requirements

When Playwright verification is complete, the evidence report must include:

```markdown
## Playwright Verification

- URL verified: [URL]
- Verification date: YYYY-MM-DD HH:MM
- Screenshot (initial): [path from browser_take_screenshot]
- Screenshot (final): [path from browser_take_screenshot]
- Console errors: none / [list if any]
- Interactive features verified:
  - [feature 1]: PASS / FAIL
  - [feature 2]: PASS / FAIL
- Overall UI status: PASS / FAIL
```

---

## Common Issues and Fixes

**Snapshot returns empty or minimal content:**
The page may be rendering client-side only. Use `browser_wait_for` with a
known text string before taking the snapshot.

**Navigation to internal URL fails (connection refused):**
Verify the service is deployed and Traefik is routing correctly. Run
`platform_preflight.py --services` first.

**Screenshot path not returned:**
The screenshot is saved to a temp path by the MCP server. If the path is not
visible in the tool output, use `browser_console_messages` to check for errors,
then retry the screenshot.

**Browser already has a page open from a previous step:**
Use `browser_navigate` with the new URL — it replaces the current page.
Use `browser_tabs` to inspect open tabs if unexpected state is present.

---

## Future: Automated Playwright Test Scripts

The agent workflow above requires a human + agent session to run.
Automated Playwright scripts that run independently (CI-style, no human present)
are planned as a future deliverable. They will:

- Be triggered by the validate suite (validate_{service}.py or a separate validate_ui.py)
- Use the same verification steps as the agent workflow, but scripted in Python
- Require the frontend architecture to be decided first

**Trigger:** After Shogun frontend planning session completes.
See: `outputs/planning/platform-test-standard-plan.md` Future Actions section.

---

## Playwright MCP Tool Reference

Quick reference for tools used in this workflow:

| Tool | Purpose |
|:-----|:--------|
| `browser_navigate` | Open a URL in the browser |
| `browser_snapshot` | Capture accessibility tree (text + structure) |
| `browser_take_screenshot` | Capture visual screenshot |
| `browser_click` | Click an element by description |
| `browser_fill_form` | Fill and submit a form |
| `browser_wait_for` | Wait for text or element to appear |
| `browser_console_messages` | Read JavaScript console output |
| `browser_network_requests` | Inspect HTTP requests made by the page |
| `browser_close` | Close the browser session |
| `browser_tabs` | List open browser tabs |

Full tool schemas: loaded via MCP server at session start.
