# Deployment Guide

## Prerequisites on svcnode-01

- Docker Engine + Docker Compose plugin installed
- Git installed, SSH key added to `github.com/ibbygithub`
- User in the `docker` group (or running as root)

## First-Time Setup

```bash
# Clone the repo
git clone git@github.com:ibbygithub/platform.git /opt/git/work/platform
cd /opt/git/work/platform
```

## Start Traefik (do this first — creates platform_net)

```bash
cd /opt/git/work/platform/infra/compose

# Add your TLS certificates to traefik/certs/
# (see traefik/dynamic/tls.yml for expected filenames)

docker compose -f docker-compose.infra.yml up -d
docker compose -f docker-compose.infra.yml ps
```

## Start Each Service

For each service, copy `.env.example` → `.env`, fill in credentials, then start:

```bash
cd /opt/git/work/platform/services/telegram-gateway
cp .env.example .env
# edit .env: TELEGRAM_BOT_TOKEN, ALLOWED_USER_IDS, UPSTREAM_URL
docker compose up --build -d

cd /opt/git/work/platform/services/places-google
cp .env.example .env
# edit .env: GOOGLE_PLACES_API_KEY, PGPASSWORD
docker compose up --build -d

cd /opt/git/work/platform/services/llm-gateway
cp .env.example .env
# edit .env: OPENAI_API_KEY, GOOGLE_API_KEY, ANTHROPIC_API_KEY
docker compose up --build -d

cd /opt/git/work/platform/services/reddit-gateway
cp .env.example .env
# edit .env: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET
docker compose up --build -d

cd /opt/git/work/platform/services/scraper
cp .env.example .env
# edit .env: FIRECRAWL_API_KEY (set to any string you choose)
docker compose up --build -d
```

## Database Setup (run once on dbnode-01)

```bash
# From your laptop or svcnode-01 — connect to dbnode-01
psql -h dbnode-01 -U dba-agent -d platform_v1 \
  -f /opt/git/work/platform/services/places-google/sql/001_create_places_schema.sql
```

If the `platform_v1` database doesn't exist yet:
```bash
psql -h dbnode-01 -U dba-agent -c "CREATE DATABASE platform_v1;"
```

## Verify All Services

```bash
curl -s http://localhost/health -H "Host: places.platform.ibbytech.com"
curl -s http://localhost/health -H "Host: llm.platform.ibbytech.com"
curl -s http://localhost/health -H "Host: reddit.platform.ibbytech.com"
curl -s http://localhost/health -H "Host: scrape.platform.ibbytech.com"
```

Or with DNS set up:
```bash
for svc in places llm reddit scrape; do
  echo -n "$svc: "; curl -sf https://${svc}.platform.ibbytech.com/health || echo "FAIL"
done
```

## Updating a Service

```bash
cd /opt/git/work/platform
git pull origin main
cd services/<service-name>
docker compose up --build -d
```

Docker Compose rebuilds only the changed service image and restarts the container.

## Viewing Logs

```bash
# All containers for a service
docker compose logs -f

# Specific container
docker logs -f platform-llm-gateway
docker logs -f platform-telegram-gateway
docker logs -f platform-places-google
docker logs -f platform-reddit-gateway
docker logs -f platform-scraper-api
```

## Traefik Dashboard

Available at `http://traefik.platform.ibbytech.com:8080` (localhost only, not routed through Traefik itself for security).

Or via SSH tunnel from your laptop:
```bash
ssh -L 8080:localhost:8080 devops-agent@svcnode-01
# Then open: http://localhost:8080
```

## Switching Telegram to Webhook Mode

When Cloudflare Tunnel is live and `telegram.platform.ibbytech.com` resolves publicly:

```bash
# On svcnode-01, edit the .env file
cd /opt/git/work/platform/services/telegram-gateway
vim .env
# Change: TELEGRAM_MODE=webhook
# Set: WEBHOOK_DOMAIN=https://telegram.platform.ibbytech.com
# Set: WEBHOOK_PATH=/webhook

# Restart the gateway
docker compose up -d

# Register the webhook with Telegram
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://telegram.platform.ibbytech.com/webhook"
```
