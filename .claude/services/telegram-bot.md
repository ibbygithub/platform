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

## Known Limitations / Quirks
- Telegram enforces a 30-message-per-second rate limit per bot
- Long messages (>4096 characters) must be split before sending
- The gateway does not currently handle inbound webhook routing — outbound only

## Last Updated
2026-03-03 — Initial doc created
