import os
import time
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

FIRECRAWL_URL     = os.getenv("FIRECRAWL_URL",     "http://firecrawl-api:3002").rstrip("/")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")

app = FastAPI(title="Platform Scraper", version="0.1.0")


def _fc_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if FIRECRAWL_API_KEY:
        headers["Authorization"] = f"Bearer {FIRECRAWL_API_KEY}"
    return headers


# ===== Models =====

class ScrapeRequest(BaseModel):
    url:          str
    formats:      Optional[List[str]] = Field(default=["markdown"])
    include_tags: Optional[List[str]] = None   # CSS selectors / tag names to keep
    exclude_tags: Optional[List[str]] = None   # CSS selectors / tag names to strip
    wait_for_ms:  Optional[int]       = None   # milliseconds to wait for JS rendering


class CrawlRequest(BaseModel):
    url:       str
    max_depth: Optional[int]       = Field(default=2,  ge=1, le=10)
    limit:     Optional[int]       = Field(default=10, ge=1, le=100)
    formats:   Optional[List[str]] = Field(default=["markdown"])


class MapRequest(BaseModel):
    url:    str
    limit:  Optional[int] = Field(default=50, ge=1, le=500)


# ===== Routes =====

@app.get("/health")
def health() -> Dict[str, Any]:
    firecrawl_ok = False
    try:
        r = requests.get(f"{FIRECRAWL_URL}/", timeout=5)
        firecrawl_ok = r.status_code == 200
    except Exception:
        pass
    return {"ok": True, "time": int(time.time()), "firecrawl_reachable": firecrawl_ok}


@app.post("/v1/scrape")
def scrape(req: ScrapeRequest) -> Dict[str, Any]:
    """Scrape a single URL. Returns markdown content and page metadata."""
    payload: Dict[str, Any] = {"url": req.url, "formats": req.formats}
    if req.include_tags:
        payload["includeTags"] = req.include_tags
    if req.exclude_tags:
        payload["excludeTags"] = req.exclude_tags
    if req.wait_for_ms:
        payload["waitFor"] = req.wait_for_ms

    try:
        r = requests.post(f"{FIRECRAWL_URL}/v1/scrape", headers=_fc_headers(), json=payload, timeout=60)
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail={"source": "firecrawl", "status": r.status_code, "body": r.text})
        data = r.json()
        return {"ok": True, "url": req.url, "data": data.get("data", data)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/crawl")
def crawl(req: CrawlRequest) -> Dict[str, Any]:
    """Crawl a site up to max_depth levels, returning content from up to limit pages."""
    payload: Dict[str, Any] = {
        "url":           req.url,
        "maxDepth":      req.max_depth,
        "limit":         req.limit,
        "scrapeOptions": {"formats": req.formats},
    }
    try:
        r = requests.post(f"{FIRECRAWL_URL}/v1/crawl", headers=_fc_headers(), json=payload, timeout=120)
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail={"source": "firecrawl", "status": r.status_code, "body": r.text})
        data = r.json()
        return {"ok": True, "url": req.url, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/map")
def map_site(req: MapRequest) -> Dict[str, Any]:
    """Return a list of URLs found on a site (site map discovery)."""
    payload: Dict[str, Any] = {"url": req.url, "limit": req.limit}
    try:
        r = requests.post(f"{FIRECRAWL_URL}/v1/map", headers=_fc_headers(), json=payload, timeout=60)
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail={"source": "firecrawl", "status": r.status_code, "body": r.text})
        data = r.json()
        return {"ok": True, "url": req.url, "links": data.get("links", [])}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
