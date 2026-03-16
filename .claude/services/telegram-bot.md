# Service: Telegram Bot Gateway

## Status
Active

## What This Service Does
Provides outbound messaging, notifications, and bot command handling via Telegram.
Use this for any task that needs to send messages, alerts, or interactive responses
to a Telegram chat or channel.

## Endpoint
- **FQDN:** `https://telegram.platform.ibbytech.com`
- **Fallback IP:** `http://192.168.71.220` (use if DNS fails)
- **Target Node:** svcnode-01
- **Reverse Proxy:** Traefik

## Authentication
- **Method:** Bot Father Token
- **Env Variable:** `TG_BOT_TOKEN`
- **Scope:** Send messages, handle commands, manage bot interactions

## Call Context

| Where You Are | URL to Use |
|:---|:---|
| Laptop (dev/test) | `https://telegram.platform.ibbytech.com` |
| brainnode-01 (production app) | `https://telegram.platform.ibbytech.com` or fallback IP |
| Inside svcnode-01 container | Internal Docker network name |

## Consumption (Python)

```python
import os
import requests

def send_telegram_message(chat_id: str, message: str) -> dict:
    """Send a message via the IbbyTech Telegram Bot gateway."""
    endpoint = os.getenv("TG_GATEWAY_URL", "https://telegram.platform.ibbytech.com")
    bot_token = os.getenv("TG_BOT_TOKEN")

    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }

    response = requests.post(f"{endpoint}/send", headers=headers, json=payload)
    response.raise_for_status()
    return response.json()

# Example: Send a notification
send_telegram_message(chat_id="YOUR_CHAT_ID", message="*Alert:* Task completed.")
```

## Observability
- **Loki Label:** `{service="telegram-bot-gateway"}`
- **Grafana Dashboard:** Not yet configured
- Outbound message delivery and errors are logged

## Capabilities

Capability registry for Stage 2 Part B (Capability Pre-check).

| Capability | Our Endpoint | Status | Last Verified |
|:-----------|:-------------|:-------|:--------------|
| Receive text messages from Telegram users | Bot polling / webhook | `implemented` | 2026-03-11 |
| Receive location shares (initial + live) | Bot polling / webhook | `implemented` | 2026-03-11 |
| Receive photos, documents, voice messages | Bot polling / webhook | `implemented` | 2026-03-11 |
| Forward message to upstream URL as JSON envelope | gateway.js → UPSTREAM_URL | `implemented` | 2026-03-11 |
| Reply to user if upstream returns reply_text | Auto-reply on upstream response | `implemented` | 2026-03-11 |
| Allowlist filtering (user IDs + group IDs) | Env var config | `implemented` | 2026-03-11 |
| Outbound send API (platform calls gateway to send) | Not exposed | `not-available` | 2026-03-11 |
| Inbound webhook HTTP endpoint | Polling mode only (default) | `available-upstream` | 2026-03-11 |
| Structured Loki logging | Not implemented | `not-available` | 2026-03-11 |

**Architecture note:** The Telegram gateway is a receiving bot, not an outbound
send API. To send messages programmatically, call the Telegram Bot API directly
with the bot token, or implement an outbound send endpoint in a separate service.

**Observability gap:** gateway.js has no Loki push code. Container stdout is the
only log source. Adding Loki logging requires a Node.js Loki client library
(separate task).

**Upstream envelope schema:** See `services/telegram-gateway/openapi.yaml` for
the full JSON schema that the gateway POSTs to UPSTREAM_URL on each message.

**Last Updated:** 2026-03-11 — Platform Test Standard Phase 3 applied. Upstream
envelope OpenAPI spec added. Validate script added at
`services/telegram-gateway/validate_telegram.py`.

---

## Known Limitations / Quirks
- Telegram enforces a 30-message-per-second rate limit per bot
- Long messages (>4096 characters) must be split before sending
- The gateway does not currently handle inbound webhook routing — outbound only

## Last Updated
2026-03-03 — Initial doc created
