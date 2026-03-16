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

## Capabilities

Capability registry for Stage 2 Part B (Capability Pre-check).

| Capability | Our Endpoint | Provider(s) | Status | Last Verified |
|:-----------|:-------------|:------------|:-------|:--------------|
| Text embeddings (1536-dim) | `POST /v1/embeddings` | openai (text-embedding-3-small) | `implemented` | 2026-03-11 |
| Text embeddings (768-dim) | `POST /v1/embeddings` | google (text-embedding-004) | `implemented` | 2026-03-11 |
| Chat completion | `POST /v1/chat` | google (gemini-2.0-flash) — default | `implemented` | 2026-03-11 |
| Chat completion | `POST /v1/chat` | openai (gpt-4o, gpt-4o-mini) | `implemented` | 2026-03-11 |
| Chat completion | `POST /v1/chat` | anthropic (claude-sonnet-4-6, etc.) | `implemented` | 2026-03-11 |
| Multi-turn conversation (system + user + assistant) | `POST /v1/chat` | all providers | `implemented` | 2026-03-11 |
| Streaming responses | Not exposed | — | `not-available` | 2026-03-11 |
| Function calling / tool use | Not exposed | — | `available-upstream` | 2026-03-11 |
| Vision (image input) | Not exposed | — | `available-upstream` | 2026-03-11 |
| Structured Loki logging (token usage, cost) | Not implemented | — | `not-available` | 2026-03-11 |

**Status definitions:**
- `implemented` — available and tested in the platform gateway
- `available-upstream` — supported by provider APIs but not yet exposed in app.py
- `not-available` — not implemented; no current plan

**Observability gap (HIGH PRIORITY):** app.py has no Loki push code. Token usage,
latency, and cost per provider cannot be monitored from Grafana. This is a billing
visibility gap. Adding Loki logging to `/v1/chat` and `/v1/embeddings` is recommended
as a priority follow-up task.

**Default routing:** Google Gemini is the default chat provider (fastest, low cost).
OpenAI is the default embed provider (1536-dim, pgvector compatible). Override with
`provider` field in the request body.

**Last Updated:** 2026-03-11 — Platform Test Standard Phase 3 applied. OpenAPI spec
added at `services/llm-gateway/openapi.yaml`. Validate script added at
`services/llm-gateway/validate_llm.py`.

---

## Known Limitations / Quirks
- Model availability depends on upstream provider API status
- Token limits vary by model — check provider docs for context window size
- All requests are logged including prompt content — do not send sensitive PII

## Last Updated
2026-03-03 — Initial doc created
