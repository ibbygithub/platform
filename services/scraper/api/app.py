import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────

FIRECRAWL_API_URL = (
    os.getenv("FIRECRAWL_API_URL") or os.getenv("FIRECRAWL_URL") or "http://firecrawl-api:3002"
).rstrip("/")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")

LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://platform-llm-gateway:8080").rstrip("/")
EMBED_PROVIDER  = os.getenv("EMBED_PROVIDER",  "openai")
EMBED_MODEL     = os.getenv("EMBED_MODEL",     "text-embedding-3-small")
EMBED_MAX_CHARS = 8000  # truncation limit before sending to embedding API

PG_CONFIG = {
    "host":            os.getenv("PGHOST",     "dbnode-01"),
    "port":            int(os.getenv("PGPORT", "5432")),
    "dbname":          os.getenv("PGDATABASE", "platform_v1"),
    "user":            os.getenv("PGUSER",     "scraper_app"),
    "password":        os.getenv("PGPASSWORD", ""),
    "connect_timeout": 10,
}
# Persistence is enabled when PGPASSWORD is set; silently disabled otherwise.
PERSIST_ENABLED = bool(PG_CONFIG["password"])

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
log = logging.getLogger("scraper")

app = FastAPI(title="Platform Scraper", version="0.2.0")


# ──────────────────────────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    url:          str
    formats:      Optional[List[str]] = Field(default=["markdown"])
    include_tags: Optional[List[str]] = None
    exclude_tags: Optional[List[str]] = None
    wait_for_ms:  Optional[int]       = None


class CrawlRequest(BaseModel):
    url:       str
    max_depth: Optional[int]       = Field(default=2,  ge=1, le=10)
    limit:     Optional[int]       = Field(default=10, ge=1, le=100)
    formats:   Optional[List[str]] = Field(default=["markdown"])


class MapRequest(BaseModel):
    url:    str
    limit:  Optional[int] = Field(default=50, ge=1, le=500)


class ExtractRequest(BaseModel):
    urls:       List[str]
    prompt:     Optional[str]            = None
    schema_def: Optional[Dict[str, Any]] = Field(default=None)


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _fc_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if FIRECRAWL_API_KEY:
        headers["Authorization"] = f"Bearer {FIRECRAWL_API_KEY}"
    return headers


def _db() -> Optional[Any]:
    """Open a new DB connection. Returns None if persistence is disabled."""
    if not PERSIST_ENABLED:
        return None
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        conn.autocommit = False
        return conn
    except Exception as exc:
        log.warning("DB connect failed (persistence skipped): %s", exc)
        return None


def _embed(text: str) -> Optional[List[float]]:
    """Call the LLM Gateway to embed text. Returns None on any failure."""
    if not text or not LLM_GATEWAY_URL:
        return None
    try:
        r = requests.post(
            f"{LLM_GATEWAY_URL}/v1/embeddings",
            json={
                "provider": EMBED_PROVIDER,
                "model":    EMBED_MODEL,
                "input":    [text[:EMBED_MAX_CHARS]],
            },
            timeout=30,
        )
        if r.status_code == 200:
            vectors = r.json().get("vectors", [])
            return vectors[0] if vectors else None
        log.warning("Embedding API returned %s: %s", r.status_code, r.text[:200])
    except Exception as exc:
        log.warning("Embedding failed (stored without vector): %s", exc)
    return None


def _safe_persist(conn, sql: str, params: tuple) -> None:
    """Execute a DB write; commit or rollback without raising."""
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        log.warning("DB write failed (result still returned to caller): %s", exc)


# ──────────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> Dict[str, Any]:
    firecrawl_ok = False
    try:
        r = requests.get(f"{FIRECRAWL_API_URL}/", timeout=5)
        firecrawl_ok = r.status_code == 200
    except Exception:
        pass

    db_ok = False
    if PERSIST_ENABLED:
        try:
            conn = psycopg2.connect(**PG_CONFIG)
            conn.close()
            db_ok = True
        except Exception:
            pass

    return {
        "ok":                  True,
        "time":                int(time.time()),
        "firecrawl_reachable": firecrawl_ok,
        "db_connected":        db_ok,
        "persist_enabled":     PERSIST_ENABLED,
        "embed_provider":      EMBED_PROVIDER,
        "embed_model":         EMBED_MODEL,
    }


@app.post("/v1/scrape")
def scrape(req: ScrapeRequest) -> Dict[str, Any]:
    """Scrape a single URL. Auto-persists result + embedding to scraper.scrape_results."""
    payload: Dict[str, Any] = {"url": req.url, "formats": req.formats}
    if req.include_tags:
        payload["includeTags"] = req.include_tags
    if req.exclude_tags:
        payload["excludeTags"] = req.exclude_tags
    if req.wait_for_ms:
        payload["waitFor"] = req.wait_for_ms

    try:
        r = requests.post(
            f"{FIRECRAWL_API_URL}/v1/scrape",
            headers=_fc_headers(), json=payload, timeout=60,
        )
        if r.status_code >= 400:
            raise HTTPException(status_code=502,
                detail={"source": "firecrawl", "status": r.status_code, "body": r.text})
        data     = r.json().get("data", {})
        metadata = data.get("metadata", {})
        title    = metadata.get("title") or data.get("title", "")
        markdown = data.get("markdown", "")
        html     = data.get("html", "")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # ── Persist + embed (non-fatal side-effect) ───────────────────────────────
    embedding = _embed(markdown or title)
    conn      = _db()
    emb_json = json.dumps(embedding) if embedding else None
    _safe_persist(conn,
        """INSERT INTO scraper.scrape_results
               (url, title, markdown, html, metadata, embedding_json, embedding)
           VALUES (%s, %s, %s, %s, %s, %s, %s::vector)""",
        (req.url, title, markdown, html,
         json.dumps(metadata), emb_json, emb_json),
    )
    if conn:
        conn.close()

    return {"ok": True, "url": req.url, "data": data}


@app.post("/v1/crawl")
def crawl(req: CrawlRequest) -> Dict[str, Any]:
    """Crawl a site up to limit pages. Polls async Firecrawl job, then persists each page + embedding."""
    payload: Dict[str, Any] = {
        "url":           req.url,
        "maxDepth":      req.max_depth,
        "limit":         req.limit,
        "scrapeOptions": {"formats": req.formats},
    }
    try:
        r = requests.post(
            f"{FIRECRAWL_API_URL}/v1/crawl",
            headers=_fc_headers(), json=payload, timeout=30,
        )
        if r.status_code >= 400:
            raise HTTPException(status_code=502,
                detail={"source": "firecrawl", "status": r.status_code, "body": r.text})
        init   = r.json()
        job_id = init.get("id") or init.get("jobId")
        if not job_id:
            pages = init.get("data", init)
        else:
            deadline = time.time() + 300
            pages    = []
            while time.time() < deadline:
                time.sleep(3)
                poll = requests.get(
                    f"{FIRECRAWL_API_URL}/v1/crawl/{job_id}",
                    headers=_fc_headers(), timeout=30,
                )
                if poll.status_code >= 400:
                    raise HTTPException(status_code=502,
                        detail={"source": "firecrawl_poll", "job_id": job_id,
                                "status": poll.status_code, "body": poll.text})
                status_data = poll.json()
                status      = status_data.get("status", "")
                if status == "completed":
                    pages = status_data.get("data", [])
                    break
                if status in ("failed", "cancelled"):
                    raise HTTPException(status_code=502,
                        detail={"source": "firecrawl_crawl", "job_id": job_id, "status": status})
            else:
                raise HTTPException(status_code=504,
                    detail=f"Crawl job {job_id} did not complete within 5 minutes")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # ── Persist + embed each page (non-fatal) ─────────────────────────────────
    session_id = str(uuid.uuid4())
    conn       = _db()
    for page in pages:
        page_url  = (page.get("metadata") or {}).get("sourceURL") or page.get("url", "")
        pg_status = str((page.get("metadata") or {}).get("statusCode", "") or "")
        markdown  = page.get("markdown", "")
        metadata  = page.get("metadata", {})
        embedding = _embed(markdown)
        emb_json  = json.dumps(embedding) if embedding else None
        _safe_persist(conn,
            """INSERT INTO scraper.crawl_results
                   (session_id, url, status, markdown, metadata, embedding_json, embedding)
               VALUES (%s, %s, %s, %s, %s, %s, %s::vector)""",
            (session_id, page_url, pg_status or None, markdown,
             json.dumps(metadata), emb_json, emb_json),
        )
    if conn:
        conn.close()

    return {"ok": True, "url": req.url, "session_id": session_id,
            "total": len(pages), "data": pages}


@app.post("/v1/map")
def map_site(req: MapRequest) -> Dict[str, Any]:
    """Discover all URLs on a site. Auto-persists URL list to scraper.map_results."""
    payload: Dict[str, Any] = {"url": req.url, "limit": req.limit}
    try:
        r = requests.post(
            f"{FIRECRAWL_API_URL}/v1/map",
            headers=_fc_headers(), json=payload, timeout=60,
        )
        if r.status_code >= 400:
            raise HTTPException(status_code=502,
                detail={"source": "firecrawl", "status": r.status_code, "body": r.text})
        links = r.json().get("links", [])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # ── Persist URL list (no embedding — URL lists don't need semantic search) ─
    conn = _db()
    _safe_persist(conn,
        """INSERT INTO scraper.map_results (root_url, url_count, urls)
           VALUES (%s, %s, %s)""",
        (req.url, len(links), json.dumps(links)),
    )
    if conn:
        conn.close()

    return {"ok": True, "url": req.url, "links": links}


@app.post("/v1/extract")
def extract(req: ExtractRequest) -> Dict[str, Any]:
    """Extract structured data via Firecrawl LLM. Auto-persists result + embedding."""
    payload: Dict[str, Any] = {"urls": req.urls}
    if req.prompt:
        payload["prompt"] = req.prompt
    if req.schema_def:
        payload["schema"] = req.schema_def

    try:
        r = requests.post(
            f"{FIRECRAWL_API_URL}/v1/extract",
            headers=_fc_headers(), json=payload, timeout=120,
        )
        if r.status_code >= 400:
            raise HTTPException(status_code=502,
                detail={"source": "firecrawl", "status": r.status_code, "body": r.text})
        init      = r.json()
        job_id    = init.get("id") or init.get("jobId")
        extracted = init.get("data")

        if job_id and not extracted:
            deadline = time.time() + 180
            while time.time() < deadline:
                time.sleep(3)
                poll = requests.get(
                    f"{FIRECRAWL_API_URL}/v1/extract/{job_id}",
                    headers=_fc_headers(), timeout=30,
                )
                if poll.status_code >= 400:
                    raise HTTPException(status_code=502,
                        detail={"source": "firecrawl_extract_poll", "job_id": job_id,
                                "status": poll.status_code, "body": poll.text})
                sd     = poll.json()
                status = sd.get("status", "")
                if status == "completed":
                    extracted = sd.get("data")
                    break
                if status in ("failed", "cancelled"):
                    raise HTTPException(status_code=502,
                        detail={"source": "firecrawl_extract", "job_id": job_id, "status": status})
            else:
                raise HTTPException(status_code=504,
                    detail=f"Extract job {job_id} did not complete within 3 minutes")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # ── Persist + embed (non-fatal) ───────────────────────────────────────────
    embed_text = json.dumps(extracted) if extracted else ""
    embedding  = _embed(embed_text)
    conn       = _db()
    emb_json = json.dumps(embedding) if embedding else None
    for url in req.urls:
        _safe_persist(conn,
            """INSERT INTO scraper.extract_results
                   (url, schema_def, extracted, embedding_json, embedding)
               VALUES (%s, %s, %s, %s, %s::vector)""",
            (url, json.dumps(req.schema_def), json.dumps(extracted),
             emb_json, emb_json),
        )
    if conn:
        conn.close()

    return {"ok": True, "urls": req.urls, "data": extracted}
