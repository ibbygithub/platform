# Service: Valkey

**Version:** 1.0.0
**Node:** svcnode-01
**FQDN:** `valkey.platform.ibbytech.com` (resolves to 192.168.71.220)
**Container:** `platform-valkey`
**Port:** 6379 (published to host)
**Protocol:** Redis wire protocol (not HTTP)
**Deploy path:** `/opt/git/work/platform/services/valkey/`
**Deployed:** 2026-03-12
**Persona:** devops-agent

---

## Purpose

Shared in-memory key/value store for the IbbyTech platform. Used for session
state, conversation context, caching, and ephemeral shared data. All platform
services and application services (shogun-core, brainnode-01 apps) may consume
this service. Auth is required on all connections.

---

## Auth

Password auth via `--requirepass`. All clients must provide `VALKEY_PASSWORD`.
No unauthenticated connections are accepted.

---

## Connection

This is a TCP service — not HTTP. There are no HTTP endpoints.

| Where You Are | Connection String |
|:---|:---|
| Docker container on svcnode-01 (platform_net) | `redis://:${VALKEY_PASSWORD}@platform-valkey:6379` |
| brainnode-01 / laptop / external node | `redis://:${VALKEY_PASSWORD}@valkey.platform.ibbytech.com:6379` |
| Fallback (if DNS fails) | `redis://:${VALKEY_PASSWORD}@192.168.71.220:6379` |

---

## Storage

- **Persistence:** AOF (append-only file) — survives container restarts
- **Volume:** `platform-valkey-data` (named Docker volume on svcnode-01)
- **Data loss on:** `docker-compose down -v` (destroys volume — Red Zone, human only)

---

## Environment Variables

| Variable | Required | Description |
|:---|:---|:---|
| `VALKEY_PASSWORD` | Yes | Auth password — required for all connections |

---

## Consumption (Python)

```python
import os
import redis

def get_valkey_client() -> redis.Redis:
    """Get a Valkey client. Uses platform_net name inside Docker, FQDN externally."""
    host = os.getenv("VALKEY_HOST", "platform-valkey")
    port = int(os.getenv("VALKEY_PORT", "6379"))
    password = os.getenv("VALKEY_PASSWORD")
    return redis.Redis(host=host, port=port, password=password, decode_responses=True)
```

Set `VALKEY_HOST=valkey.platform.ibbytech.com` in `.env` for services running
outside of svcnode-01's Docker network (e.g., brainnode-01 apps).

---

## Observability

- **Loki Label:** None — Valkey logs to Docker stdout only
- **View logs:** `docker logs --tail 50 platform-valkey`
- **Metrics:** Not yet configured

---

## Capabilities

| Capability | Status | Notes |
|:-----------|:-------|:------|
| Key/value SET / GET / DEL | `implemented` | Standard Redis commands |
| TTL / EXPIRE | `implemented` | Use for session + conversation context |
| Pub/Sub | `available` | Available but not yet consumed by any service |
| Sorted sets / lists | `available` | Available but not yet consumed |

**Last Updated:** 2026-03-12 — Initial deployment

---

## Rate Limiting

No rate limiting. Single-node in-memory store. Memory limit governed by
the host node's available RAM on svcnode-01.

---

## Known Limitations / Quirks

- No TLS — traffic is unencrypted. Acceptable for internal lab network only.
  Do not expose port 6379 to the public internet.
- No cluster mode — single instance. Not HA.
- AOF persistence adds a small write overhead. Acceptable at current scale.

---

## Last Updated

2026-03-12 — Initial service deployed
