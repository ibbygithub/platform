"""
app.py
IbbyTech Platform MVP Test Dashboard

Run:  uvicorn app:app --reload --port 8000
URL:  http://localhost:8000
"""

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

import rag
import services
import txlog

rag.init_db()

app       = FastAPI(title="IbbyTech Platform Dashboard", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

UPLOAD_DIR = Path(__file__).parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


# ── UI ────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def api_health():
    return services.health_all()


# ── Transactions log ──────────────────────────────────────────────────────────

@app.get("/api/transactions")
async def api_transactions(limit: int = 20, tab: str = None):
    """Return the last `limit` transaction records, newest first. Filter by tab if given."""
    return txlog.read_transactions(limit=limit, tab=tab or None)


# ── Documents ─────────────────────────────────────────────────────────────────

@app.get("/api/documents")
async def api_list_documents():
    return rag.list_documents()


@app.post("/api/documents/upload")
async def api_upload_document(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix!r}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    with txlog.Tx("documents", "upload") as tx:
        tx.req({"filename": file.filename, "size_bytes": len(content), "suffix": suffix})
        try:
            result = rag.ingest_document(file.filename, content)
            tx.resp(result)
        except ValueError as e:
            tx.error(str(e))
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            tx.error(str(e))
            raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

    return result


@app.delete("/api/documents/{doc_id}")
async def api_delete_document(doc_id: str):
    with txlog.Tx("documents", "delete") as tx:
        tx.req({"doc_id": doc_id})
        deleted = rag.delete_document(doc_id)
        if not deleted:
            tx.error("not found")
            raise HTTPException(status_code=404, detail="Document not found")
        result = {"ok": True, "doc_id": doc_id}
        tx.resp(result)
    return result


# ── RAG Chat ──────────────────────────────────────────────────────────────────

@app.post("/api/rag/query")
async def api_rag_query(request: Request):
    body     = await request.json()
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Missing: question")

    with txlog.Tx("rag", "query") as tx:
        tx.req({"question": question})
        try:
            result = rag.query_rag(question)
            # Log embedding sub-call detail if available
            if result.get("embedding_used"):
                tx.sub("embed_query", {
                    "input": question,
                    "vector": result.get("embedding_used"),
                })
            # Summarise sources without full chunk text in the top record
            sources_summary = [
                {
                    "filename":    s.get("filename"),
                    "chunk_index": s.get("chunk_index"),
                    "score":       s.get("score"),
                    "chunk_text":  s.get("chunk_text"),   # txlog truncates at 1000
                }
                for s in (result.get("sources") or [])
            ]
            tx.resp({
                "answer":          result.get("answer"),
                "sources_count":   len(sources_summary),
                "sources":         sources_summary,
                "model":           result.get("model"),
            })
        except Exception as e:
            tx.error(str(e))
            raise HTTPException(status_code=500, detail=f"RAG query failed: {e}")

    return result


# ── Scraper ───────────────────────────────────────────────────────────────────

@app.post("/api/scraper/scrape")
async def api_scrape(request: Request):
    body         = await request.json()
    url          = (body.get("url") or "").strip()
    wait_for_ms  = body.get("wait_for_ms")
    include_tags = [t.strip() for t in (body.get("include_tags") or "").split(",") if t.strip()] or None
    exclude_tags = [t.strip() for t in (body.get("exclude_tags") or "").split(",") if t.strip()] or None

    if not url:
        raise HTTPException(status_code=400, detail="Missing: url")

    with txlog.Tx("scraper", "scrape") as tx:
        tx.req({"url": url, "wait_for_ms": wait_for_ms,
                "include_tags": include_tags, "exclude_tags": exclude_tags})
        try:
            scraped = services.scrape_url(
                url,
                wait_for_ms=int(wait_for_ms) if wait_for_ms else None,
                include_tags=include_tags,
                exclude_tags=exclude_tags,
            )
        except Exception as e:
            tx.error(str(e))
            raise HTTPException(status_code=502, detail=f"Scraper error: {e}")

        markdown = scraped.get("markdown") or scraped.get("content") or ""
        if not markdown.strip():
            result = {"raw": "", "summary": "Scraper returned no content for this URL."}
            tx.resp({"chars": 0, "metadata": scraped.get("metadata"), "summary": result["summary"]})
            return result

        # Log raw scraper payload (markdown truncated by txlog)
        tx.sub("firecrawl_response", {
            "chars":    len(markdown),
            "markdown": markdown,
            "metadata": scraped.get("metadata"),
            "links":    scraped.get("links", [])[:20],
        })

        # Summarise via LLM gateway
        llm_messages = [
            {"role": "system", "content": "You are a concise summariser. Extract the key information from the scraped web content below in 3-5 bullet points."},
            {"role": "user",   "content": markdown[:8000]},
        ]
        try:
            summary = services.llm_chat(messages=llm_messages, max_output_tokens=512)
            tx.sub("llm_summary", {
                "messages":          llm_messages,
                "max_output_tokens": 512,
                "output":            summary,
            })
        except Exception as e:
            summary = f"(Summary failed: {e})"
            tx.sub("llm_summary", {"error": str(e)})

        result = {"raw": markdown, "summary": summary}
        tx.resp({"chars": len(markdown), "summary_chars": len(summary)})

    return result


# ── Scraper ingest ────────────────────────────────────────────────────────────

@app.post("/api/scraper/ingest")
async def api_scraper_ingest(request: Request):
    """Ingest previously scraped markdown content into the RAG document index."""
    body     = await request.json()
    content  = (body.get("content") or "").strip()
    filename = (body.get("filename") or "scraped.md").strip()

    if not content:
        raise HTTPException(status_code=400, detail="No content to ingest")

    with txlog.Tx("scraper", "ingest") as tx:
        tx.req({"filename": filename, "content_chars": len(content)})
        try:
            result = rag.ingest_document(filename, content.encode("utf-8"))
            tx.resp(result)
        except ValueError as e:
            tx.error(str(e))
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            tx.error(str(e))
            raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

    return result


# ── Scraper: crawl ────────────────────────────────────────────────────────────

@app.post("/api/scraper/crawl")
async def api_scraper_crawl(request: Request):
    """Crawl a site, returning each page as markdown. Polls until Firecrawl job completes."""
    body      = await request.json()
    url       = (body.get("url") or "").strip()
    max_depth = int(body.get("max_depth") or 2)
    limit     = int(body.get("limit") or 10)

    if not url:
        raise HTTPException(status_code=400, detail="Missing: url")
    if not 1 <= max_depth <= 10:
        raise HTTPException(status_code=400, detail="max_depth must be 1-10")
    if not 1 <= limit <= 100:
        raise HTTPException(status_code=400, detail="limit must be 1-100")

    # Auto-raise max_depth when URL's own path exceeds it (Firecrawl treats
    # depth as absolute from domain root, not relative to start URL).
    url_segments  = [s for s in urlparse(url).path.split("/") if s]
    url_own_depth = len(url_segments)
    effective_depth = max_depth
    if url_own_depth > max_depth:
        effective_depth = url_own_depth + 1

    with txlog.Tx("scraper", "crawl") as tx:
        tx.req({
            "url":              url,
            "max_depth":        max_depth,
            "effective_depth":  effective_depth,
            "url_own_depth":    url_own_depth,
            "limit":            limit,
        })
        try:
            result = services.crawl_url(url, max_depth=effective_depth, limit=limit)
        except Exception as e:
            tx.error(str(e))
            raise HTTPException(status_code=502, detail=f"Crawl error: {e}")

        pages = result.get("data", [])
        combined = "\n\n---\n\n".join(
            f"# {(p.get('metadata') or {}).get('title', p.get('url', ''))}\n\n{p.get('markdown', '')}"
            for p in pages if p.get("markdown")
        )

        page_summaries = [
            {
                "url":      (p.get("metadata") or {}).get("sourceURL") or p.get("url", ""),
                "title":    (p.get("metadata") or {}).get("title", ""),
                "chars":    len(p.get("markdown", "")),
                "markdown": p.get("markdown", ""),   # truncated by txlog
            }
            for p in pages
        ]
        tx.resp({
            "total":             result.get("total", len(pages)),
            "pages":             page_summaries,
            "combined_chars":    len(combined),
        })

    return {
        "ok":               result.get("ok", True),
        "url":              url,
        "session_id":       result.get("session_id"),
        "total":            result.get("total", len(pages)),
        "pages":            [
            {
                "url":      (p.get("metadata") or {}).get("sourceURL") or p.get("url", ""),
                "title":    (p.get("metadata") or {}).get("title", ""),
                "markdown": p.get("markdown", ""),
                "chars":    len(p.get("markdown", "")),
            }
            for p in pages
        ],
        "combined_markdown": combined,
    }


# ── Scraper: batch scrape ─────────────────────────────────────────────────────

@app.post("/api/scraper/batch_scrape")
async def api_scraper_batch(request: Request):
    """
    Scrape a list of URLs one at a time (sequential, Playwright-safe).
    Returns per-URL results and a combined markdown string for RAG ingestion.
    Max 50 URLs per request.
    """
    body     = await request.json()
    urls     = body.get("urls") or []
    wait_ms  = body.get("wait_for_ms")
    max_urls = min(int(body.get("max_urls") or 30), 50)

    if isinstance(urls, str):
        urls = [u.strip() for u in urls.split("\n") if u.strip()]
    urls = [u.strip() for u in urls if u.strip()][:max_urls]

    if not urls:
        raise HTTPException(status_code=400, detail="Missing: urls")

    with txlog.Tx("scraper", "batch_scrape") as tx:
        tx.req({"url_count": len(urls), "urls": urls, "wait_for_ms": wait_ms})

        results = []
        for url in urls:
            try:
                scraped  = services.scrape_url(url, wait_for_ms=int(wait_ms) if wait_ms else None)
                markdown = scraped.get("markdown") or scraped.get("content") or ""
                title    = (scraped.get("metadata") or {}).get("title") or url
                results.append({"url": url, "ok": True, "title": title,
                                 "markdown": markdown, "chars": len(markdown)})
            except Exception as e:
                results.append({"url": url, "ok": False, "error": str(e),
                                 "markdown": "", "chars": 0})

        successful = [r for r in results if r["ok"] and r["markdown"]]
        combined   = "\n\n---\n\n".join(
            f"# {r['title']}\nSource: {r['url']}\n\n{r['markdown']}"
            for r in successful
        )

        resp_payload = {
            "ok":               True,
            "total":            len(urls),
            "succeeded":        len(successful),
            "failed":           len(results) - len(successful),
            "results":          results,       # markdown fields truncated by txlog
            "combined_chars":   len(combined),
        }
        tx.resp(resp_payload)

    return {
        "ok":               True,
        "total":            len(urls),
        "succeeded":        len(successful),
        "failed":           len(results) - len(successful),
        "results":          results,
        "combined_markdown": combined,
    }


# ── Scraper: map ──────────────────────────────────────────────────────────────

@app.post("/api/scraper/map")
async def api_scraper_map(request: Request):
    """Discover all URLs on a site without scraping content."""
    body  = await request.json()
    url   = (body.get("url") or "").strip()
    limit = int(body.get("limit") or 50)

    if not url:
        raise HTTPException(status_code=400, detail="Missing: url")

    with txlog.Tx("scraper", "map") as tx:
        tx.req({"url": url, "limit": limit})
        try:
            result = services.map_url(url, limit=limit)
        except Exception as e:
            tx.error(str(e))
            raise HTTPException(status_code=502, detail=f"Map error: {e}")

        links = result.get("links", [])
        tx.resp({"ok": result.get("ok", True), "total": len(links), "links": links})

    return {"ok": result.get("ok", True), "url": url, "links": links, "total": len(links)}


# ── Scraper: extract ──────────────────────────────────────────────────────────

@app.post("/api/scraper/extract")
async def api_scraper_extract(request: Request):
    """Extract structured data from one or more URLs using an LLM prompt."""
    body   = await request.json()
    urls   = body.get("urls") or []
    prompt = (body.get("prompt") or "").strip()

    if isinstance(urls, str):
        urls = [u.strip() for u in urls.split("\n") if u.strip()]

    if not urls:
        raise HTTPException(status_code=400, detail="Missing: urls")
    if not prompt:
        raise HTTPException(status_code=400, detail="Missing: prompt")

    with txlog.Tx("scraper", "extract") as tx:
        tx.req({"urls": urls, "prompt": prompt})
        try:
            result = services.extract_url(urls, prompt=prompt)
            tx.resp({"ok": result.get("ok", True), "data": result.get("data")})
        except Exception as e:
            tx.error(str(e))
            raise HTTPException(status_code=502, detail=f"Extract error: {e}")

    return {"ok": result.get("ok", True), "urls": urls, "data": result.get("data")}


# ── Places ────────────────────────────────────────────────────────────────────

@app.post("/api/places/search")
async def api_places_search(request: Request):
    body      = await request.json()
    query     = (body.get("query") or "").strip()
    location  = (body.get("location") or "").strip()
    lat       = body.get("lat")
    lng       = body.get("lng")
    radius_m  = int(body.get("radius_m") or 5000)
    max_res   = int(body.get("max_results") or 10)

    if not query:
        raise HTTPException(status_code=400, detail="Missing: query")

    min_rating = body.get("min_rating")
    if min_rating is not None:
        min_rating = float(min_rating)

    with txlog.Tx("places", "search") as tx:
        tx.req({"query": query, "location": location, "lat": lat, "lng": lng,
                "radius_m": radius_m, "max_results": max_res, "min_rating": min_rating})

        if location:
            try:
                lat, lng = services.geocode(location)
                tx.sub("nominatim_geocode", {"location": location, "lat": lat, "lng": lng})
            except Exception as e:
                tx.error(f"Geocode failed: {e}")
                raise HTTPException(status_code=422, detail=f"Could not geocode location '{location}': {e}")
        elif lat is None or lng is None:
            raise HTTPException(status_code=400, detail="Provide a location or explicit lat/lng")

        fetch_count = min(20, max_res * 4) if min_rating is not None else max_res
        try:
            places = services.places_search(query, float(lat), float(lng), radius_m, fetch_count)
            tx.sub("places_api_response", {
                "fetched":    len(places),
                "places_raw": places,   # photos omitted by truncation rules; full data logged
            })
        except Exception as e:
            tx.error(str(e))
            raise HTTPException(status_code=502, detail=f"Places error: {e}")

        if min_rating is not None:
            places = [p for p in places if (p.get("rating") or 0) >= min_rating]
        places = places[:max_res]

        response = {
            "places":            places,
            "resolved_location": {"lat": lat, "lng": lng},
            "total_fetched":     fetch_count,
            "after_filter":      len(places),
            "min_rating_applied": min_rating,
        }
        tx.resp({"after_filter": len(places), "total_fetched": fetch_count,
                 "resolved_lat": lat, "resolved_lng": lng})

    return response
