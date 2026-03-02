# Telegram Gateway

Receives events from a Telegram bot and forwards them as structured JSON envelopes to a configurable upstream HTTP endpoint. This is a pure ingress gateway — it does not interpret messages or contain any application logic.

## Endpoints

| FQDN | Purpose |
|------|---------|
| `telegram.platform.ibbytech.com` | Webhook receiver (when `TELEGRAM_MODE=webhook`) |

## Quick Start

```bash
cp .env.example .env    # fill in BOT_TOKEN, ALLOWED_USER_IDS, UPSTREAM_URL
docker compose up --build -d
```

## Modes

### Polling (default — works on LAN without a public IP)
The bot connects out to Telegram. No inbound connection needed.
```
TELEGRAM_MODE=polling
```

### Webhook (requires public HTTPS — use when Cloudflare Tunnel is live)
Telegram calls your HTTPS URL. Flip this variable and Traefik handles the rest.
```
TELEGRAM_MODE=webhook
WEBHOOK_DOMAIN=https://telegram.platform.ibbytech.com
WEBHOOK_PATH=/webhook
WEBHOOK_PORT=3000
```

## Event Envelope

Every Telegram event is wrapped in the same structure before forwarding:

```json
{
  "receipt_id": "a3f1bc2d8e4f5a6b",
  "received_at": "2026-03-02T10:00:00.000Z",
  "kind": "text | location | photo | document | voice",
  "update": { "update_id": 12345678 },
  "from":    { "user_id": 123456789, "username": "alice", ... },
  "chat":    { "id": 123456789, "type": "private", ... },
  "message": { "message_id": 42, "date": 1709380800, ... },
  "capabilities": { "can_search": false, "can_scrape": false, "can_fetch_files": false },
  "payload": { ... }
}
```

The `payload` field varies by `kind`:
- **text** → `{ "text": "...", "entities": [] }`
- **location** → `{ "location": { "latitude": ..., "longitude": ..., ... } }`
- **photo** → `{ "caption": "...", "photos": [ {...} ] }`
- **document** → `{ "caption": "...", "document": {...} }`
- **voice** → `{ "voice": {...} }`

Live location updates (`edited_message`) arrive as `kind: "location"` envelopes.

## Upstream Response

If the upstream returns `{ "reply_text": "..." }`, the gateway sends that text back to the user. Empty `{}` means no reply. For live location updates, the gateway is silent unless `reply_text` is present.

## Access Control

- `ALLOWED_USER_IDS` — required, comma-separated Telegram numeric user IDs
- `ALLOWED_GROUP_IDS` — optional, required for group/supergroup messages
- Private chat: user must be in `ALLOWED_USER_IDS`
- Group chat: user must be in `ALLOWED_USER_IDS` **and** group in `ALLOWED_GROUP_IDS`

## `/status` Command

Any allowed user can send `/status` to the bot to confirm the gateway is alive.
