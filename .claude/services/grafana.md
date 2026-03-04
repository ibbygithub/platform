# Service: Grafana (Observability Dashboards)

## Status
Active — Dashboard build-out in progress

## What This Service Does
Grafana is the visualization and alerting layer for the IbbyTech platform.
It connects to Loki for log-based dashboards and is the primary interface for
monitoring service health, API usage, error rates, and billing metrics.

## Endpoint
- **Internal endpoint:** `http://192.168.71.220:3000`
- **Target Node:** svcnode-01
- **Note:** Grafana is not exposed externally — internal network only

## Authentication
- **Method:** Username / Password (web UI login)
- **Env Variable:** `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD`
- **Access:** Browser-based UI only — no programmatic write access required for
  service consumers

## What Agents Should Know About Grafana

Grafana is a **read and configuration** surface, not a write surface for application code.

When writing a new service, your responsibility is to:
1. Ensure your service emits logs to Loki with correct labels (see `loki.md`)
2. Note in the service doc whether a Grafana dashboard exists for it
3. Flag missing dashboards with: `⚠️ Grafana Dashboard: Not yet configured`

Do not attempt to create Grafana dashboards programmatically unless explicitly asked.

## Current Dashboard Status

| Service | Dashboard | Status |
|:---|:---|:---|
| Google Places Gateway | — | Not yet configured |
| Telegram Bot Gateway | — | Not yet configured |
| LLM Gateway | — | Not yet configured |
| Loki (self) | — | Not yet configured |
| Platform Health | — | Not yet configured |

## Observability
- **Loki Label:** `{service="grafana"}`
- Grafana emits its own logs to Loki

## Known Limitations / Quirks
- Dashboard build-out is in progress — most services do not yet have dashboards
- Alerting rules have not been configured yet
- Grafana is on internal network only — VPN or SSH tunnel required for remote access

## Last Updated
2026-03-03 — Initial doc created
