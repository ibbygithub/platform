# Evidence: Tavily Gateway Deployment Validation
**Date:** 2026-03-13
**Persona:** devops-agent
**Node:** svcnode-01 (192.168.71.220)
**Service:** platform-tavily
**FQDN:** tavily.platform.ibbytech.com

---

## Deployment Summary

Tavily web search gateway deployed from platform repo `develop` branch.
Service runs on Docker / platform_net, routed via Traefik on port 8084.

---

## Green Gate — 7/7 PASSED

| Check | Result | Detail |
|:------|:-------|:-------|
| TAVILY_API_KEY configured | ✅ PASS | env var present and non-default |
| Container running | ✅ PASS | platform-tavily is up |
| TCP port 8084 | ✅ PASS | 127.0.0.1:8084 reachable (2ms) |
| /health endpoint | ✅ PASS | returned ok=true (1286ms) |
| Search (English query) | ✅ PASS | returned 2 results (1242ms) |
| Search (kanji query) | ✅ PASS | returned 2 results (1452ms) |
| Domain search (tabelog.com) | ✅ PASS | 3 tabelog.com results (1287ms) |

---

## Issues Resolved During Deployment

1. **docker-compose pull error** — Docker attempted registry pull of `platform-tavily` image before local build. Fixed with `pull_policy: never` in docker-compose.yml.
2. **TCP check failing** — No host port binding. Fixed with `ports: 127.0.0.1:8084:8084`. Localhost only — Traefik handles all external traffic.
3. **python command not found** — Debian 11 uses `python3`. Validation run with `python3 validate_tavily.py`.

---

## Outcome

✅ TAVILY GATEWAY LIVE — `tavily.platform.ibbytech.com` ready for shogun-core consumption.
