# Service: LLM Gateway

## Status
Active

## What This Service Does
Provides unified access to multiple LLM providers (OpenAI, Anthropic, and others)
through a single internal endpoint. Use this for any task requiring AI completions,
embeddings, or model inference. Never call LLM provider APIs directly — route
through this gateway for consistent auth, logging, and billing tracking.

## Endpoint
- **FQDN:** `https://llm.platform.ibbytech.com`
- **Fallback IP:** `http://192.168.71.220` (use if DNS fails)
- **Target Node:** svcnode-01
- **Reverse Proxy:** Traefik

## Authentication
- **Method:** API Key
- **Env Variable:** `LLM_GATEWAY_KEY`
- **Scope:** All model providers routed through the gateway

## Call Context

| Where You Are | URL to Use |
|:---|:---|
| Laptop (dev/test) | `https://llm.platform.ibbytech.com` |
| brainnode-01 (production app) | `https://llm.platform.ibbytech.com` or fallback IP |
| Inside svcnode-01 container | Internal Docker network name |

## Consumption (Python)

```python
import os
import requests

def llm_completion(prompt: str, model: str = "gpt-4o") -> str:
    """Request a completion via the IbbyTech LLM gateway."""
    endpoint = os.getenv("LLM_GATEWAY_URL", "https://llm.platform.ibbytech.com")
    api_key = os.getenv("LLM_GATEWAY_KEY")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1000
    }

    response = requests.post(f"{endpoint}/v1/chat/completions",
                             headers=headers, json=payload)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

# Example
result = llm_completion("Summarize the top 3 ramen shops in Osaka.", model="gpt-4o")
```

## Observability
- **Loki Label:** `{service="llm-gateway"}`
- **Grafana Dashboard:** Not yet configured
- Token usage, model, latency, and cost are logged per request — critical for billing

## Known Limitations / Quirks
- Model availability depends on upstream provider API status
- Token limits vary by model — check provider docs for context window size
- All requests are logged including prompt content — do not send sensitive PII

## Last Updated
2026-03-03 — Initial doc created
