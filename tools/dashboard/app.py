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
    body = await request.json()
    url  = (body.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="Missing: url")

    try:
        scraped = services.scrape_url(url)
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


# ── Places ────────────────────────────────────────────────────────────────────

@app.post("/api/places/search")
async def api_places_search(request: Request):
    body      = await request.json()
    query     = (body.get("query") or "").strip()
    lat       = body.get("lat")
    lng       = body.get("lng")
    radius_m  = int(body.get("radius_m") or 5000)
    max_res   = int(body.get("max_results") or 10)

    if not query:
        raise HTTPException(status_code=400, detail="Missing: query")
    if lat is None or lng is None:
        raise HTTPException(status_code=400, detail="Missing: lat / lng")

    try:
        places = services.places_search(query, float(lat), float(lng), radius_m, max_res)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Places error: {e}")

    return {"places": places}
