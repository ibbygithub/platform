# MCP Environment 1 — Partial Install Report
Date: 2026-03-09
Outcome: PARTIAL — 2 of 4 servers installed, 2 pending credentials

## Installed

### playwright
- Package: `@playwright/mcp@latest` (v0.0.68 confirmed)
- Transport: stdio (npx on demand)
- Scope: user (global — all Claude Code sessions)
- Credentials: none required
- Status: ✅ registered in ~/.claude.json

### memory
- Package: `@modelcontextprotocol/server-memory`
- Transport: stdio (npx on demand)
- Scope: user (global — all Claude Code sessions)
- Credentials: none required
- Storage: local knowledge graph file (default)
- Status: ✅ registered in ~/.claude.json

## Pending

### github
- Endpoint: https://api.githubcopilot.com/mcp/ (HTTP transport)
- Blocked on: GitHub Personal Access Token
- Required scopes: repo, read:org, read:user, read:discussion
- Action: user creates PAT at github.com/settings/tokens → provide token → run:
  claude mcp add -s user --transport http github https://api.githubcopilot.com/mcp/ --header "Authorization: Bearer <TOKEN>"

### postgres (mcp_readonly)
- Blocked on: dba-agent credential provisioning task
- Requirement: new read-only role with SELECT on platform_v1 + shogun_v1
- Do NOT use dba-agent credentials (CREATEROLE/CREATEDB — over-privileged)
- Do NOT use mcp_shogun (shogun_v1 only — insufficient scope)
- Action: separate dba-agent task to provision mcp_readonly role, then configure:
  claude mcp add -s user -e POSTGRES_URL=postgresql://mcp_readonly:<pass>@192.168.71.221:5432/platform_v1 postgres -- npx @modelcontextprotocol/server-postgres

## Config State (verified)
~/.claude.json mcpServers key confirmed present with both installed servers.
Both packages verified via npx dry-run — playwright v0.0.68, memory starts on stdio.

## Next Session
Reconnect to complete GitHub and PostgreSQL installs after credentials are ready.
