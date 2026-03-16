# Dashboard Activity Log — Evidence Report
Date: 2026-03-08
Branch: feature/20260308-dashboard-activity-log
Outcome: COMPLETED — all GREEN

## What Was Built

### txlog.py (new)
- `Tx` context manager: times any code block, writes one JSON line on exit
- `log_transaction()` internals append to `dashboard_transactions.log`
- `read_transactions(limit, tab)` tails file newest-first, optional tab filter
- Smart truncation rules:
  - markdown/content/raw: 1000 chars + "[N more chars]" suffix
  - answer/output_text: 800 chars
  - LLM message content: 500 chars
  - Embedding vectors: {dim, preview[5 floats], l2_norm} — no 1536-float dumps
  - Crawl page markdown: 1000 chars per page

### app.py
- `GET /api/transactions?tab=<name>&limit=<n>` — new endpoint
- Every handler wrapped with `txlog.Tx(tab, operation)`
- Sub-calls logged for nested service interactions:
  - Scrape: `firecrawl_response` (raw markdown + metadata + links) + `llm_summary` (full message array + output)
  - RAG query: answer + sources with chunk_text + score
  - Places: `nominatim_geocode` (input → lat/lng) + `places_api_response` (full raw place list)
  - Documents: filename + size_bytes + ingest result (doc_id + chunk_count)

### index.html
- `<template id="activity-log-tpl">` — shared panel cloned into all 4 tabs
- Dark monospace box (bg-gray-950), max-h-96 scrollable
- Each record: collapsible row — header shows op name, timestamp, latency, ok/fail dot
- Expanded body: syntax-coloured JSON (keys colour-coded by semantic meaning)
- Long string values truncated at 400 chars in the rendered view
- `_withLog()` wraps all operation functions — fires `refreshActivityLog()` 300ms after completion
- Clear button: resets display only, does not touch the log file

## Test Results

| Tab | Operation | Record Written | Sub-calls |
|:---|:---|:---|:---|
| Scraper | scrape (triggers URL) | OK 2609ms | firecrawl_response + llm_summary |
| RAG | query | OK 1984ms | sources list with scores |
| Places | search (Shibuya coffee) | OK 1609ms | nominatim_geocode + places_api_response |
| Documents | (wired, not tested separately) | wired | filename + chunk_count |

HTML checks: all 7 elements present in rendered page (61342 chars).
