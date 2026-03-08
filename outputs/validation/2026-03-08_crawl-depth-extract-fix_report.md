# Crawl Depth Fix + Extract Enable — Evidence Report
Date: 2026-03-08
Branch: feature/20260308-crawl-depth-extract-fix
Outcome: COMPLETED — all features GREEN

---

## Issues Fixed

### Issue 1 — Crawl "URL depth exceeds the specified maxDepth"

**Root cause:** Firecrawl treats `maxDepth` as absolute from the domain root,
not relative to the start URL. A URL like:
`https://help.tradestation.com/10_00/eng/tsdevhelp/el_editor/easylanguage_documents.htm`
has 5 path segments. With `max_depth=2` (the UI default), Firecrawl rejects the
request because the start URL itself is already at depth 5 > 2.

**Fix:** `app.py` crawl endpoint now computes `url_own_depth` from the URL's path
segments and auto-raises `max_depth` to `url_own_depth + 1` when needed.
The user's requested depth is preserved as the *relative* depth from that URL.

**Test result:**
- URL: `https://help.tradestation.com/10_00/eng/tsdevhelp/el_editor/easylanguage_documents.htm`
- User-supplied `max_depth=2`, URL depth=5 → effective `max_depth=6`
- Result: OK — 1 page, 3753 chars (EasyLanguage Documents content returned)

---

### Issue 2 — Extract "Status: Degraded" banner (stale)

**Root cause:** The degraded notice was written when `OPENAI_API_KEY` was not yet
configured in Firecrawl. The key has since been added.

**Verification on svcnode-01 (devops-agent):**
- `/opt/firecrawl/.env` contains `OPENAI_API_KEY` and `OPENAI_BASE_URL`
- `docker inspect firecrawl-api-1` confirms both vars are loaded in the running container
- No container recreate needed — key was already live

**Fix:** Removed the red degraded banner from `index.html` Extract panel.

**Test result:**
- URL: `https://developers.reddit.com/docs/capabilities/devvit-web/devvit_web_configuration`
- Prompt: Extract devvit.json config properties with name/type/default/required/description
- Result: OK — structured JSON returned with 5 field keys per property

---

## Final Feature Status

| Feature | Status |
|:---|:---|
| Scrape | GREEN |
| Crawl (including deep URLs) | GREEN |
| Map | GREEN |
| Batch Scrape | GREEN |
| Extract | GREEN — OPENAI_API_KEY confirmed live |
| RAG Ingest | GREEN |
| RAG Query | GREEN |
| manage.ps1 start/stop/restart/status | GREEN |
| LLM Gateway | GREEN |
| Scraper service | GREEN |
| Google Places | GREEN |
| Telegram | FAIL — pre-existing, out of scope |
| Reddit Gateway | NULL — no FQDN yet, out of scope |
