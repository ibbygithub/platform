# Service: {Service Name}

**Version:** 1.0.0
**Node:** svcnode-01
**FQDN:** `{service-slug}.platform.ibbytech.com`
**Container:** `platform-{service-slug}`
**Port (internal):** {port}
**Deploy path:** `/opt/git/work/platform/services/{service-slug}/`
**Deployed:** YYYY-MM-DD
**Persona:** devops-agent

---

## Purpose

{One paragraph describing what this service does and what problem it solves.
State who the consumers are — other platform services, AI agents, brainnode-01 apps, etc.}

---

## Auth

{Describe authentication method. Options: None (open on platform_net), Bearer token (env var name), API key (env var name).}

---

## Endpoint

- **FQDN:** `https://{service-slug}.platform.ibbytech.com`
- **Fallback IP:** `http://192.168.71.220` (use if DNS fails)
- **Target Node:** svcnode-01
- **Reverse Proxy:** Traefik

## Call Context

| Where You Are | URL to Use |
|:---|:---|
| Laptop (dev/test) | `https://{service-slug}.platform.ibbytech.com` |
| brainnode-01 (production app) | `https://{service-slug}.platform.ibbytech.com` or fallback IP |
| Inside svcnode-01 container | `http://platform-{service-slug}:{port}` (Docker network name) |

---

## Endpoints

| Method | Path | Description |
|:---|:---|:---|
| GET | `/health` | Health check — status, DB connectivity, config summary |
| POST | `/v1/{resource}` | {description} |

---

## Request Examples

```json
POST /v1/{resource}
{"field": "value"}
```

---

## Storage

**Database:** {platform_v1 / shogun_v1 / none}
**Schema:** {schema name}
**User:** {app user}

| Table | Contents |
|:---|:---|
| `{schema}.{table}` | {description} |

---

## Environment Variables

| Variable | Required | Description |
|:---|:---|:---|
| `{VAR_NAME}` | Yes | {description} |
| `PGPASSWORD` | Yes / No | App user password — enables persistence |
| `PGHOST` | No | Default: `dbnode-01` |
| `PGDATABASE` | No | Default: `platform_v1` |
| `PGUSER` | No | Default: `{app_user}` |
| `LLM_GATEWAY_URL` | No | Default: `http://platform-llm-gateway:8080` |

---

## Consumption (Python)

```python
import os
import requests

def call_{service_slug}(param: str) -> dict:
    """Call the IbbyTech {Service Name} gateway."""
    endpoint = os.getenv("{SERVICE}_GATEWAY_URL", "https://{service-slug}.platform.ibbytech.com")
    api_key = os.getenv("{SERVICE}_API_KEY")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {"param": param}

    response = requests.post(f"{endpoint}/v1/{resource}", headers=headers, json=payload)
    response.raise_for_status()
    return response.json()
```

---

## Observability

- **Loki Label:** `{service="{service-slug}"}`
- **Grafana Dashboard:** Not yet configured
- {Describe what is logged — requests, errors, latency, upstream calls}

---

## Capabilities

Capability registry for Stage 2 Part B (Capability Pre-check). Before building
any feature that depends on this service, check this table.

| Capability | Our Endpoint | Status | Last Verified |
|:-----------|:-------------|:-------|:--------------|\
| {capability description} | `{METHOD /path}` | `implemented` | YYYY-MM-DD |
| {capability description} | Not exposed | `available-upstream` | YYYY-MM-DD |
| {capability description} | Not implemented | `not-available` | YYYY-MM-DD |

**Status definitions:**
- `implemented` — available and tested in the platform gateway
- `available-upstream` — supported by the upstream provider API but not yet
  exposed in this gateway. Document the gap; task scope may expand to add it.
- `not-available` — not implemented; no upstream path or not planned

**Last Updated:** YYYY-MM-DD — {brief description of what was done / verified}

---

## Rate Limiting

{Describe rate limits — upstream provider limits, self-imposed throttling, backoff behaviour.
If no rate limiting: state "No rate limiting. Upstream provider limits apply."}

---

## Known Limitations / Quirks

- {Known limitation or quirk}
- {Any architectural constraints callers should know about}

---

## Last Updated

YYYY-MM-DD — Initial doc created
