import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_API_URL = "https://api.tavily.com"

LOKI_URL = os.getenv("LOKI_URL", "http://192.168.71.220:3100")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
log = logging.getLogger("tavily")

app = FastAPI(title="Platform Tavily Gateway", version="1.0.0")


# ──────────────────────────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query:               str
    search_depth:        Optional[str]       = Field(default="basic", pattern="^(basic|advanced)$")
    max_results:         Optional[int]       = Field(default=5, ge=1, le=20)
    include_domains:     Optional[List[str]] = None   # e.g. ["tabelog.com"] for restaurant search
    exclude_domains:     Optional[List[str]] = None
    include_answer:      Optional[bool]      = False   # Tavily AI summary of results
    include_raw_content: Optional[bool]      = False
    include_images:      Optional[bool]      = False


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _loki(level: str, msg: str, **labels: str) -> None:
    """Push a structured log entry to Loki. Non-fatal — never raises."""
    stream: Dict[str, str] = {"service": "tavily", "level": level, "node": "svcnode-01"}
    stream.update({k: str(v) for k, v in labels.items() if v is not None})
    try:
        requests.post(
            f"{LOKI_URL}/loki/api/v1/push",
            json={"streams": [{"stream": stream, "values": [[str(time.time_ns()), msg]]}]},
            timeout=3,
        )
    except Exception:
        pass  # Loki failure must never affect the caller


# ──────────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> Dict[str, Any]:
    """Verify that TAVILY_API_KEY is configured and Tavily is reachable."""
    if not TAVILY_API_KEY:
        return {
            "ok":             False,
            "time":           int(time.time()),
            "tavily_key_set": False,
            "error":          "TAVILY_API_KEY not configured",
        }

    # Probe Tavily with a minimal search — cheapest way to verify the key works.
    try:
        r = requests.post(
            f"{TAVILY_API_URL}/search",
            json={
                "api_key":      TAVILY_API_KEY,
                "query":        "health check",
                "search_depth": "basic",
                "max_results":  1,
            },
            timeout=10,
        )
        tavily_ok = r.status_code == 200
        tavily_status = r.status_code
    except Exception as exc:
        tavily_ok = False
        tavily_status = str(exc)

    return {
        "ok":             tavily_ok,
        "time":           int(time.time()),
        "tavily_key_set": True,
        "tavily_status":  tavily_status,
    }


@app.post("/v1/search")
def search(req: SearchRequest) -> Dict[str, Any]:
    """
    Web search via Tavily.

    Supports kanji + English queries. Use include_domains to restrict results
    (e.g. ["tabelog.com"] for restaurant-only searches).

    search_depth:
      - "basic"    — fast, good for most queries (~1-2s)
      - "advanced" — deeper crawl, higher quality but slower (~5-10s)
    """
    if not TAVILY_API_KEY:
        raise HTTPException(status_code=503, detail="TAVILY_API_KEY not configured")

    t0          = time.time()
    status_code = "200"

    try:
        payload: Dict[str, Any] = {
            "api_key":            TAVILY_API_KEY,
            "query":              req.query,
            "search_depth":       req.search_depth,
            "max_results":        req.max_results,
            "include_answer":     req.include_answer,
            "include_raw_content": req.include_raw_content,
            "include_images":     req.include_images,
        }
        if req.include_domains:
            payload["include_domains"] = req.include_domains
        if req.exclude_domains:
            payload["exclude_domains"] = req.exclude_domains

        try:
            r = requests.post(
                f"{TAVILY_API_URL}/search",
                json=payload,
                timeout=30,  # advanced search can be slow
            )
            if r.status_code == 401:
                raise HTTPException(status_code=502, detail="Tavily rejected API key — check TAVILY_API_KEY")
            if r.status_code >= 400:
                raise HTTPException(
                    status_code=502,
                    detail={"source": "tavily", "status": r.status_code, "body": r.text[:500]},
                )
            data = r.json()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        return {
            "ok":           True,
            "query":        req.query,
            "results":      data.get("results", []),
            "images":       data.get("images", []),
            "answer":       data.get("answer"),
            "response_time": data.get("response_time"),
        }

    except HTTPException as exc:
        status_code = str(exc.status_code)
        raise
    except Exception:
        status_code = "500"
        raise
    finally:
        latency = int((time.time() - t0) * 1000)
        _loki(
            "error" if status_code != "200" else "info",
            f'POST /v1/search "{req.query}" -> {status_code} {latency}ms',
            method="POST",
            endpoint="/v1/search",
            query=req.query[:100],
            status_code=status_code,
            latency_ms=str(latency),
        )
