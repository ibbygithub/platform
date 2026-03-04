# Service: [Service Name]

## Status
Active | Degraded | Planned

## What This Service Does
[One to two sentences. What does this service provide? When should an agent use it?]

## Endpoint
- **FQDN:** `https://[name].platform.ibbytech.com`
- **Fallback IP:** `http://192.168.71.220`
- **Target Node:** svcnode-01
- **Reverse Proxy:** Traefik

## Authentication
- **Method:** Bearer Token | API Key | Bot Token | None
- **Env Variable:** `SERVICE_API_KEY`
- **Scope:** [What access does this credential grant?]

## Call Context

| Where You Are | URL to Use |
|:---|:---|
| Laptop (dev/test) | `https://[name].platform.ibbytech.com` |
| brainnode-01 (production app) | `https://[name].platform.ibbytech.com` or fallback IP |
| Inside svcnode-01 container | Internal Docker network name |

## Consumption (Python)

```python
import os
import requests

def call_service(param: str) -> dict:
    """[One line description of what this function does.]"""
    endpoint = os.getenv("SERVICE_GATEWAY_URL", "https://[name].platform.ibbytech.com")
    api_key = os.getenv("SERVICE_API_KEY")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "param": param
    }

    response = requests.post(f"{endpoint}/[route]", headers=headers, json=payload)
    response.raise_for_status()
    return response.json()

# Example usage
result = call_service("example input")
```

## Observability
- **Loki Label:** `{service="[service-slug]"}`
- **Grafana Dashboard:** Not yet configured | [URL if configured]

## Known Limitations / Quirks
- [List anything an agent needs to know before using this service]
- [Rate limits, caching behavior, known failure modes, etc.]
- If none known at time of writing: "None documented yet."

## Last Updated
YYYY-MM-DD — [What was added or changed]
