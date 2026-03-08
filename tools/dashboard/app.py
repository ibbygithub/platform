"""
app.py
IbbyTech Platform MVP Test Dashboard

Run:  uvicorn app:app --reload --port 8000
URL:  http://localhost:8000
"""

import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

import rag
import services

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

    try:
        result = rag.ingest_document(file.filename, content)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

    return result


@app.delete("/api/documents/{doc_id}")
async def api_delete_document(doc_id: str):
    deleted = rag.delete_document(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"ok": True, "doc_id": doc_id}


# ── RAG Chat ──────────────────────────────────────────────────────────────────

@app.post("/api/rag/query")
async def api_rag_query(request: Request):
    body = await request.json()
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Missing: question")

    try:
        result = rag.query_rag(question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG query failed: {e}")

    return result


# ── Scraper ───────────────────────────────────────────────────────────────────

@app.post("/api/scraper/scrape")
async def api_scrape(request: Request):
    body        = await request.json()
    url         = (body.get("url") or "").strip()
    wait_for_ms = body.get("wait_for_ms")
    include_tags = [t.strip() for t in (body.get("include_tags") or "").split(",") if t.strip()] or None
    exclude_tags = [t.strip() for t in (body.get("exclude_tags") or "").split(",") if t.strip()] or None

    if not url:
        raise HTTPException(status_code=400, detail="Missing: url")

    try:
        scraped = services.scrape_url(
            url,
            wait_for_ms=int(wait_for_ms) if wait_for_ms else None,
            include_tags=include_tags,
            exclude_tags=exclude_tags,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scraper error: {e}")

    markdown = scraped.get("markdown") or scraped.get("content") or ""
    if not markdown.strip():
        return {"raw": "", "summary": "Scraper returned no content for this URL."}

    # Summarise the scraped content via LLM gateway
    try:
        summary = services.llm_chat(
            messages=[
                {"role": "system", "content": "You are a concise summariser. Extract the key information from the scraped web content below in 3-5 bullet points."},
                {"role": "user",   "content": markdown[:8000]},
            ],
            max_output_tokens=512,
        )
    except Exception as e:
        summary = f"(Summary failed: {e})"

    return {"raw": markdown, "summary": summary}


# ── Scraper ingest ────────────────────────────────────────────────────────────

@app.post("/api/scraper/ingest")
async def api_scraper_ingest(request: Request):
    """Ingest previously scraped markdown content into the RAG document index."""
    body     = await request.json()
    content  = (body.get("content") or "").strip()
    filename = (body.get("filename") or "scraped.md").strip()

    if not content:
        raise HTTPException(status_code=400, detail="No content to ingest")

    try:
        result = rag.ingest_document(filename, content.encode("utf-8"))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
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
        raise HTTPException(status_code=400, detail="max_depth must be 1–10")
    if not 1 <= limit <= 100:
        raise HTTPException(status_code=400, detail="limit must be 1–100")

    try:
        result = services.crawl_url(url, max_depth=max_depth, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Crawl error: {e}")

    pages = result.get("data", [])
    # Build a combined markdown document for RAG ingestion
    combined = "\n\n---\n\n".join(
        f"# {(p.get('metadata') or {}).get('title', p.get('url', ''))}\n\n{p.get('markdown', '')}"
        for p in pages if p.get("markdown")
    )
    return {
        "ok":         result.get("ok", True),
        "url":        url,
        "session_id": result.get("session_id"),
        "total":      result.get("total", len(pages)),
        "pages":      [
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


# ── Scraper: map ──────────────────────────────────────────────────────────────

@app.post("/api/scraper/map")
async def api_scraper_map(request: Request):
    """Discover all URLs on a site without scraping content."""
    body  = await request.json()
    url   = (body.get("url") or "").strip()
    limit = int(body.get("limit") or 50)

    if not url:
        raise HTTPException(status_code=400, detail="Missing: url")

    try:
        result = services.map_url(url, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Map error: {e}")

    links = result.get("links", [])
    return {"ok": result.get("ok", True), "url": url, "links": links, "total": len(links)}


# ── Scraper: extract ──────────────────────────────────────────────────────────

@app.post("/api/scraper/extract")
async def api_scraper_extract(request: Request):
    """Extract structured data from one or more URLs using an LLM prompt."""
    body   = await request.json()
    urls   = body.get("urls") or []
    prompt = (body.get("prompt") or "").strip()

    # Accept a single url string as a convenience
    if isinstance(urls, str):
        urls = [u.strip() for u in urls.split("\n") if u.strip()]

    if not urls:
        raise HTTPException(status_code=400, detail="Missing: urls")
    if not prompt:
        raise HTTPException(status_code=400, detail="Missing: prompt")

    try:
        result = services.extract_url(urls, prompt=prompt)
    except Exception as e:
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

    # Geocode if location string provided; otherwise fall back to explicit lat/lng
    min_rating = body.get("min_rating")  # optional float, e.g. 4.7
    if min_rating is not None:
        min_rating = float(min_rating)

    if location:
        try:
            lat, lng = services.geocode(location)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Could not geocode location '{location}': {e}")
    elif lat is None or lng is None:
        raise HTTPException(status_code=400, detail="Provide a location (e.g. 'Tokyo, Japan') or explicit lat/lng")

    # Fetch more candidates when filtering by rating so we have enough to work with
    fetch_count = min(20, max_res * 4) if min_rating is not None else max_res
    try:
        places = services.places_search(query, float(lat), float(lng), radius_m, fetch_count)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Places error: {e}")

    if min_rating is not None:
        places = [p for p in places if (p.get("rating") or 0) >= min_rating]

    places = places[:max_res]

    return {
        "places": places,
        "resolved_location": {"lat": lat, "lng": lng},
        "total_fetched": fetch_count,
        "after_filter": len(places),
        "min_rating_applied": min_rating,
    }
