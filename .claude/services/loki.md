# Service: Loki (Log Aggregation)

## Status
Active — Full build-out in progress

## What This Service Does
Loki is the centralized log aggregation service for the IbbyTech platform.
All services on all nodes should emit structured logs to Loki. This supports
security auditing, billing reconciliation, troubleshooting, and support.

This is infrastructure — do not bypass it. If a service you write does not
log to Loki, mark it explicitly as incomplete.

## Endpoint
- **Internal endpoint:** `http://192.168.71.220:3100`
- **Target Node:** svcnode-01
- **Note:** Loki is not exposed externally — internal network only

## Authentication
- **Method:** None (internal network, no auth required currently)
- **Env Variable:** `LOKI_URL` → `http://192.168.71.220:3100`

## Consumption (Python — Push Logs via HTTP)

```python
import os
import time
import requests

LOKI_URL = os.getenv("LOKI_URL", "http://192.168.71.220:3100")

def push_log(service_name: str, message: str, level: str = "info") -> None:
    """Push a structured log entry to Loki."""
    payload = {
        "streams": [
            {
                "stream": {"service": service_name, "level": level},
                "values": [
                    [str(time.time_ns()), message]
                ]
            }
        ]
    }
    response = requests.post(f"{LOKI_URL}/loki/api/v1/push", json=payload)
    response.raise_for_status()

# Example
push_log("google-places-gateway", "Search request: ramen Osaka — 200 OK", level="info")
push_log("telegram-bot-gateway", "Message delivery failed — chat_id not found", level="error")
```

## Standard Log Labels

Every service must include these labels in its log streams:

| Label | Description | Example |
|:---|:---|:---|
| `service` | Service name slug | `google-places-gateway` |
| `level` | Log level | `info`, `warn`, `error` |
| `node` | Source node | `svcnode-01`, `brainnode-01` |

Additional labels for API gateway calls:

| Label | Description |
|:---|:---|
| `method` | HTTP method |
| `status_code` | Response code |
| `latency_ms` | Response time |

## Observability
- **Loki Label:** `{service="loki"}` (self-referential — Loki logs its own health)
- **Grafana Dashboard:** Not yet configured

## Known Limitations / Quirks
- Full build-out is in progress — not all services are emitting logs yet
- Loki does not store logs indefinitely — retention policy not yet configured
- If Loki is unreachable, log to local file as fallback — do not silently drop logs

## Last Updated
2026-03-03 — Initial doc created
