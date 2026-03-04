#!/usr/bin/env python3
"""
validate_firecrawl.py
=====================
End-to-end validation of all four Firecrawl features with result persistence
to Postgres on dbnode-01.

Steps
-----
  0  Environment discovery (printed at startup)
  1  DB pre-test: connect, list tables, baseline row counts
  2  Scrape — single URL
  3  Map   — site structure
  4  Crawl — 10-page multi-page crawl
  5  Extract — structured LLM extraction
  6  Final report: pass/fail, delta row counts, elapsed time

Prerequisites
-------------
  pip install requests psycopg2-binary

Environment variables (see .env.test.example):
  SCRAPER_URL        URL of the platform scraper API
                     default: https://scrape.platform.ibbytech.com
  FIRECRAWL_API_KEY  API key for the scraper service
  PGHOST             default: dbnode-01
  PGPORT             default: 5432
  PGDATABASE         default: platform_v1
  PGUSER             default: scraper_app
  PGPASSWORD         (required)

Usage
-----
  cp .env.test.example .env.test
  # fill in PGPASSWORD and FIRECRAWL_API_KEY
  set -a; source .env.test; set +a   # Linux/Mac
  # On Windows: set each variable manually or use a .env loader

  python validate_firecrawl.py
"""

import json
import os
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# Dependency check
# ──────────────────────────────────────────────────────────────────────────────
_missing = []
try:
    import requests
except ImportError:
    _missing.append("requests")
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    _missing.append("psycopg2-binary")

if _missing:
    print(f"[FATAL] Missing dependencies: {', '.join(_missing)}")
    print(f"        Run:  pip install {' '.join(_missing)}")
    sys.exit(1)

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────
SCRAPER_URL       = os.environ.get("SCRAPER_URL", "https://scrape.platform.ibbytech.com").rstrip("/")
FIRECRAWL_API_URL = os.environ.get("FIRECRAWL_API_URL", "http://host.docker.internal:3002").rstrip("/")
FC_API_KEY        = os.environ.get("FIRECRAWL_API_KEY", "")

PG_CONFIG = {
    "host":     os.environ.get("PGHOST",     "dbnode-01"),
    "port":     int(os.environ.get("PGPORT", "5432")),
    "dbname":   os.environ.get("PGDATABASE", "platform_v1"),
    "user":     os.environ.get("PGUSER",     "scraper_app"),
    "password": os.environ.get("PGPASSWORD", ""),
    "connect_timeout": 10,
}

# ──────────────────────────────────────────────────────────────────────────────
# Test targets
# ──────────────────────────────────────────────────────────────────────────────
SCRAPE_URL  = "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
MAP_URL     = "https://books.toscrape.com"
CRAWL_URL   = "https://books.toscrape.com"
EXTRACT_URL = "https://books.toscrape.com/catalogue/page-1.html"
CRAWL_LIMIT = 10

EXTRACT_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "book_title":   {"type": "string", "description": "The title of the book"},
            "price":        {"type": "string", "description": "The listed price (e.g. '£51.77')"},
            "star_rating":  {"type": "string", "description": "Star rating word (One/Two/Three/Four/Five)"},
            "availability": {"type": "string", "description": "Stock status (e.g. 'In stock')"},
        },
        "required": ["book_title", "price"],
    },
}

SCRAPER_TABLES = [
    "scraper.scrape_results",
    "scraper.map_results",
    "scraper.crawl_results",
    "scraper.extract_results",
]

# ──────────────────────────────────────────────────────────────────────────────
# Globals
# ──────────────────────────────────────────────────────────────────────────────
_suite_start  = time.time()
_results: Dict[str, Dict[str, Any]] = {}  # step -> {pass, error, detail}
_db_conn      = None  # shared connection


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _hdr(title: str) -> None:
    width = 72
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def _ok(msg: str) -> None:
    print(f"  [PASS] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def _info(msg: str) -> None:
    print(f"  [INFO] {msg}")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _elapsed() -> str:
    return f"{time.time() - _suite_start:.1f}s"


def _scraper_headers() -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if FC_API_KEY:
        h["Authorization"] = f"Bearer {FC_API_KEY}"
    return h


def _get_db() -> Any:
    """Return the shared DB connection, or raise with a clear message."""
    global _db_conn
    if _db_conn is None or _db_conn.closed:
        raise RuntimeError("No database connection available.")
    return _db_conn


def _row_counts(cur, tables: List[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for t in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            counts[t] = cur.fetchone()[0]
        except Exception:
            counts[t] = -1  # table missing or inaccessible
    return counts


def _check_db_connection() -> Optional[str]:
    """Return error string if DB is not reachable, else None."""
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        conn.close()
        return None
    except Exception as exc:
        return str(exc)


def _check_scraper_health() -> Tuple[bool, str]:
    """Return (ok, detail)."""
    try:
        r = requests.get(f"{SCRAPER_URL}/health", headers=_scraper_headers(), timeout=10)
        data = r.json()
        return r.status_code == 200, json.dumps(data)
    except Exception as exc:
        return False, str(exc)


def _check_firecrawl_direct() -> Tuple[bool, int, str]:
    """Hit the Firecrawl root endpoint directly. Returns (ok, http_status, body)."""
    try:
        r = requests.get(f"{FIRECRAWL_API_URL}/", timeout=8)
        return r.status_code == 200, r.status_code, r.text.strip()
    except Exception as exc:
        return False, 0, str(exc)


def _record_failure(step: str, exc: Exception, halt: bool = True) -> None:
    """Print error info, check connectivity, log to DB if available, then halt."""
    _fail(f"Step {step} FAILED")
    print()
    traceback.print_exc()

    print()
    print("  ── Connectivity diagnostics ─────────────────────────────────")
    db_err = _check_db_connection()
    if db_err:
        print(f"  [DIAG] dbnode-01 postgres:  UNREACHABLE — {db_err}")
    else:
        print(f"  [DIAG] dbnode-01 postgres:  reachable")

    scraper_ok, scraper_detail = _check_scraper_health()
    print(f"  [DIAG] scraper API health:  {'OK' if scraper_ok else 'FAILED'} — {scraper_detail}")
    fc_key_set = bool(FC_API_KEY)
    print(f"  [DIAG] FIRECRAWL_API_KEY:   {'set' if fc_key_set else 'NOT SET (empty)'}")

    _results[step] = {"pass": False, "error": str(exc), "detail": traceback.format_exc()}

    # Try to log the failure to the DB
    try:
        conn = _get_db()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scraper.extract_results (url, schema_def, extracted)
                VALUES (%s, %s, %s)
                """,
                (
                    f"validation_failure:step_{step}",
                    json.dumps({"error": str(exc)}),
                    json.dumps({"step": step, "error": str(exc), "traceback": traceback.format_exc()}),
                ),
            )
        conn.commit()
        print("  [DIAG] Failure logged to scraper.extract_results.")
    except Exception:
        print("  [DIAG] Could not log failure to DB (connection unavailable).")

    if halt:
        print()
        print("  Halting — fix the issue above and re-run.")
        _print_final_report(partial=True)
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# Step 0 — Environment Discovery
# ──────────────────────────────────────────────────────────────────────────────

def step0_environment():
    _hdr("Step 0 — Environment Discovery")
    _info(f"SCRAPER_URL       = {SCRAPER_URL}")
    _info(f"FIRECRAWL_API_URL = {FIRECRAWL_API_URL}")
    _info(f"FIRECRAWL_API_KEY = {'local-no-auth (self-hosted, auth disabled)' if FC_API_KEY == 'local-no-auth' else ('*** (set)' if FC_API_KEY else '(not set)')}")
    _info(f"PGHOST            = {PG_CONFIG['host']}")
    _info(f"PGPORT            = {PG_CONFIG['port']}")
    _info(f"PGDATABASE        = {PG_CONFIG['dbname']}")
    _info(f"PGUSER            = {PG_CONFIG['user']}")
    _info(f"PGPASSWORD        = {'*** (set)' if PG_CONFIG['password'] else '(not set — connection will likely fail)'}")

    if not PG_CONFIG["password"]:
        print()
        _fail("PGPASSWORD is not set. Set it in your environment before running.")
        sys.exit(1)

    # ── Direct Firecrawl connectivity check ───────────────────────────────────
    print()
    _info(f"Checking Firecrawl instance directly at {FIRECRAWL_API_URL}/ ...")
    fc_ok, fc_status, fc_body = _check_firecrawl_direct()
    if fc_ok:
        _ok(f"Firecrawl reachable — HTTP {fc_status}  body: {fc_body!r}")
    else:
        _fail(f"Firecrawl NOT reachable at {FIRECRAWL_API_URL}/ — HTTP {fc_status}  error: {fc_body}")
        print()
        print("  Cannot proceed without a reachable Firecrawl instance.")
        print(f"  Verify that Firecrawl is running on svcnode-01 (192.168.71.220) port 3002")
        print(f"  and that FIRECRAWL_API_URL is set correctly.")
        sys.exit(1)

    # ── LLM provider check (required for Step 5 Extract) ─────────────────────
    openai_key    = os.environ.get("OPENAI_API_KEY", "").strip()
    ollama_url    = os.environ.get("OLLAMA_BASE_URL", "").strip()
    print()
    _info("Checking LLM provider availability (needed for Step 5 — Extract) ...")
    _info(f"  OPENAI_API_KEY  : {'set' if openai_key else 'NOT SET'}")
    _info(f"  OLLAMA_BASE_URL : {ollama_url if ollama_url else 'NOT SET'}")
    if not openai_key and not ollama_url:
        print()
        print("  ┌─────────────────────────────────────────────────────────────┐")
        print("  │  WARNING — No LLM provider configured                       │")
        print("  │                                                              │")
        print("  │  The Firecrawl instance at /opt/firecrawl on svcnode-01 has │")
        print("  │  OPENAI_API_KEY unset and no OLLAMA_BASE_URL in its .env.   │")
        print("  │                                                              │")
        print("  │  Step 5 (Extract) will fail because Firecrawl needs an LLM  │")
        print("  │  to perform structured data extraction.                      │")
        print("  │                                                              │")
        print("  │  To fix, either:                                             │")
        print("  │   1. Add OPENAI_API_KEY=<key> to /opt/firecrawl/.env on     │")
        print("  │      svcnode-01 and restart:  docker compose restart        │")
        print("  │   2. Add OLLAMA_BASE_URL=http://<host>:11434 to the same    │")
        print("  │      file (if a local Ollama instance is available)          │")
        print("  │                                                              │")
        print("  │  Steps 2–4 (Scrape / Map / Crawl) do NOT require an LLM    │")
        print("  │  and will run normally.                                      │")
        print("  └─────────────────────────────────────────────────────────────┘")
        print()
        _info("Pausing 5 seconds — press Ctrl-C now to abort before Extract runs.")
        time.sleep(5)
    else:
        _ok("LLM provider configured — Extract step should function.")

    # ── Scraper API health (via wrapper) ──────────────────────────────────────
    print()
    _info("Checking scraper API health (via wrapper) ...")
    ok, detail = _check_scraper_health()
    if ok:
        _ok(f"Scraper API is up.  {detail}")
    else:
        _fail(f"Scraper API health check failed: {detail}")
        print("       The test will continue; individual steps will fail if the API is unreachable.")


# ──────────────────────────────────────────────────────────────────────────────
# Step 1 — Database Validation (Pre-Test)
# ──────────────────────────────────────────────────────────────────────────────

def step1_db_pre_test() -> Dict[str, int]:
    _hdr("Step 1 — Database Validation (Pre-Test)")
    global _db_conn

    _info(f"Connecting to {PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['dbname']} ...")
    try:
        _db_conn = psycopg2.connect(**PG_CONFIG)
        _db_conn.autocommit = False
        _ok("Connected to Postgres on dbnode-01.")
    except Exception as exc:
        _fail(f"Cannot connect to Postgres: {exc}")
        print("       Check PGHOST, PGPORT, PGUSER, PGPASSWORD and network access.")
        sys.exit(1)

    cur = _db_conn.cursor()

    # List all tables in the scraper schema
    _info("Listing tables in 'scraper' schema ...")
    try:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'scraper'
            ORDER BY table_name
            """
        )
        existing = [r[0] for r in cur.fetchall()]
    except Exception as exc:
        _fail(f"Cannot query information_schema: {exc}")
        existing = []

    if existing:
        _ok(f"Found {len(existing)} table(s) in scraper schema: {', '.join(existing)}")
    else:
        _info("No tables found in scraper schema — schema will be created now.")

    # Create schema + tables if missing
    _info("Applying schema.sql (CREATE IF NOT EXISTS) ...")
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    if not os.path.exists(schema_path):
        _fail(f"schema.sql not found at {schema_path}")
        sys.exit(1)

    with open(schema_path, "r") as f:
        schema_sql = f.read()

    # Strip GRANT lines (may fail if user lacks GRANT privilege)
    filtered_lines = [
        ln for ln in schema_sql.splitlines()
        if not ln.strip().startswith("GRANT") and not ln.strip().startswith("-- GRANT")
    ]
    try:
        cur.execute("\n".join(filtered_lines))
        _db_conn.commit()
        _ok("Schema applied successfully.")
    except Exception as exc:
        _db_conn.rollback()
        _fail(f"Schema creation failed: {exc}")
        sys.exit(1)

    # Describe each table
    for table in SCRAPER_TABLES:
        schema, tname = table.split(".")
        try:
            cur.execute(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                """,
                (schema, tname),
            )
            cols = cur.fetchall()
            _info(f"  {table} — {len(cols)} column(s):")
            for col_name, dtype, nullable in cols:
                print(f"         {col_name:<20} {dtype:<30} nullable={nullable}")
        except Exception as exc:
            _fail(f"Could not describe {table}: {exc}")

    # Baseline row counts
    print()
    _info("Baseline row counts:")
    baseline = _row_counts(cur, SCRAPER_TABLES)
    for t, n in baseline.items():
        print(f"         {t:<42}  rows = {n if n >= 0 else 'N/A (table missing)'}")

    _results["step1"] = {"pass": True, "baseline": baseline}
    return baseline


# ──────────────────────────────────────────────────────────────────────────────
# Step 2 — Scrape (Single URL)
# ──────────────────────────────────────────────────────────────────────────────

def step2_scrape():
    _hdr("Step 2 — Scrape (Single URL)")
    _info(f"Target: {SCRAPE_URL}")
    _info("Calling POST /v1/scrape (formats: markdown, html) ...")

    try:
        t0 = time.time()
        resp = requests.post(
            f"{SCRAPER_URL}/v1/scrape",
            headers=_scraper_headers(),
            json={"url": SCRAPE_URL, "formats": ["markdown", "html"]},
            timeout=90,
        )
        elapsed = time.time() - t0

        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")

        payload = resp.json()
        data    = payload.get("data", {})

        title    = (data.get("metadata") or {}).get("title") or data.get("title", "")
        markdown = data.get("markdown", "")
        html     = data.get("html", "")
        metadata = data.get("metadata", {})

        _ok(f"Scrape completed in {elapsed:.1f}s")
        _info(f"  title          : {title!r}")
        _info(f"  markdown length: {len(markdown)} chars")
        _info(f"  html length    : {len(html)} chars")
        _info(f"  metadata keys  : {list(metadata.keys())}")

        # Persist to DB
        conn = _get_db()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scraper.scrape_results (url, title, markdown, html, metadata)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (SCRAPE_URL, title, markdown, html, json.dumps(metadata)),
            )
            row_id, created_at = cur.fetchone()
        conn.commit()
        _ok(f"Persisted to scraper.scrape_results — id={row_id}, created_at={created_at}")

        # Verify by reading it back
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id, url, title, length(markdown) AS md_len, created_at FROM scraper.scrape_results WHERE id = %s", (row_id,))
            row = cur.fetchone()
        _ok(f"Verification read: id={row['id']}, url={row['url'][:60]}, title={row['title']!r}, md_len={row['md_len']}, created_at={row['created_at']}")

        _results["step2"] = {"pass": True, "row_id": row_id}

    except Exception as exc:
        _record_failure("step2", exc)


# ──────────────────────────────────────────────────────────────────────────────
# Step 3 — Map (Site Structure)
# ──────────────────────────────────────────────────────────────────────────────

def step3_map():
    _hdr("Step 3 — Map (Site Structure)")
    _info(f"Target: {MAP_URL}")
    _info("Calling POST /v1/map (limit=500) ...")

    try:
        t0 = time.time()
        resp = requests.post(
            f"{SCRAPER_URL}/v1/map",
            headers=_scraper_headers(),
            json={"url": MAP_URL, "limit": 500},
            timeout=90,
        )
        elapsed = time.time() - t0

        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")

        payload = resp.json()
        links   = payload.get("links", [])
        count   = len(links)

        _ok(f"Map completed in {elapsed:.1f}s — discovered {count} URLs")

        # Persist to DB
        conn = _get_db()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scraper.map_results (root_url, url_count, urls)
                VALUES (%s, %s, %s)
                RETURNING id, created_at
                """,
                (MAP_URL, count, json.dumps(links)),
            )
            row_id, created_at = cur.fetchone()
        conn.commit()
        _ok(f"Persisted to scraper.map_results — id={row_id}, url_count={count}, created_at={created_at}")

        # Verify: read back and print first 10 URLs
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT id, root_url, url_count, urls FROM scraper.map_results WHERE id = %s",
                (row_id,),
            )
            row = cur.fetchone()

        db_urls = row["urls"] if isinstance(row["urls"], list) else json.loads(row["urls"])
        _ok(f"Verification read: id={row['id']}, root_url={row['root_url']}, url_count={row['url_count']}")
        print()
        _info("First 10 discovered URLs (from DB query):")
        for i, u in enumerate(db_urls[:10], 1):
            print(f"    {i:>2}.  {u}")

        _results["step3"] = {"pass": True, "row_id": row_id, "url_count": count}

    except Exception as exc:
        _record_failure("step3", exc)


# ──────────────────────────────────────────────────────────────────────────────
# Step 4 — Crawl (Multi-Page)
# ──────────────────────────────────────────────────────────────────────────────

def step4_crawl():
    _hdr("Step 4 — Crawl (Multi-Page)")
    _info(f"Target: {CRAWL_URL}  (limit={CRAWL_LIMIT} pages)")
    _info("Calling POST /v1/crawl — this polls until completion (up to 5 min) ...")

    session_id = uuid.uuid4()

    try:
        t0 = time.time()
        resp = requests.post(
            f"{SCRAPER_URL}/v1/crawl",
            headers=_scraper_headers(),
            json={"url": CRAWL_URL, "limit": CRAWL_LIMIT, "max_depth": 2, "formats": ["markdown"]},
            timeout=360,  # allow for internal polling (scraper polls up to 5 min)
        )
        elapsed = time.time() - t0

        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")

        payload = resp.json()
        pages   = payload.get("data", [])
        _ok(f"Crawl completed in {elapsed:.1f}s — {len(pages)} pages returned")

        # Persist each page as an individual record
        conn = _get_db()
        with conn.cursor() as cur:
            for page in pages:
                page_url = (page.get("metadata") or {}).get("sourceURL") or page.get("url", "")
                status   = (page.get("metadata") or {}).get("statusCode", "")
                markdown = page.get("markdown", "")
                metadata = page.get("metadata", {})
                cur.execute(
                    """
                    INSERT INTO scraper.crawl_results (session_id, url, status, markdown, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (str(session_id), page_url, str(status) if status else None,
                     markdown, json.dumps(metadata)),
                )
        conn.commit()
        _ok(f"Persisted {len(pages)} page records to scraper.crawl_results (session_id={session_id})")

        # Verify: confirm count and print summary table
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT url, status, content_len, created_at
                FROM scraper.crawl_results
                WHERE session_id = %s
                ORDER BY id
                """,
                (str(session_id),),
            )
            db_rows = cur.fetchall()

        _ok(f"DB query returned {len(db_rows)} record(s) for session {session_id}")
        if len(db_rows) != CRAWL_LIMIT:
            _info(f"NOTE: expected {CRAWL_LIMIT} rows; got {len(db_rows)} — Firecrawl may have found fewer pages")

        print()
        _info("Crawl summary (from DB query):")
        header = f"  {'URL':<55} {'STATUS':<8} {'CONTENT_LEN':>11}  CREATED_AT"
        print(header)
        print("  " + "-" * (len(header) - 2))
        for r in db_rows:
            url_trunc = (r["url"] or "")[:54]
            print(f"  {url_trunc:<55} {str(r['status'] or ''):<8} {str(r['content_len'] or 0):>11}  {r['created_at']}")

        _results["step4"] = {"pass": True, "session_id": str(session_id), "pages": len(db_rows)}

    except Exception as exc:
        _record_failure("step4", exc)


# ──────────────────────────────────────────────────────────────────────────────
# Step 5 — Extract (Structured Data / LLM)
# ──────────────────────────────────────────────────────────────────────────────

def step5_extract():
    _hdr("Step 5 — Extract (Structured Data / LLM)")
    _info(f"Target: {EXTRACT_URL}")
    _info("Schema: book_title, price, star_rating, availability")
    _info("Calling POST /v1/extract ...")

    if not FC_API_KEY:
        _info("FIRECRAWL_API_KEY is not set — extract may still work if Firecrawl has no auth.")

    try:
        t0 = time.time()
        resp = requests.post(
            f"{SCRAPER_URL}/v1/extract",
            headers=_scraper_headers(),
            json={
                "urls":       [EXTRACT_URL],
                "prompt":     "Extract a list of books from this page. For each book capture: book_title, price, star_rating (as a word like One/Two/Three/Four/Five), and availability.",
                "schema_def": EXTRACT_SCHEMA,
            },
            timeout=180,
        )
        elapsed = time.time() - t0

        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")

        payload   = resp.json()
        extracted = payload.get("data")

        _ok(f"Extract completed in {elapsed:.1f}s")

        # Persist to DB
        conn = _get_db()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scraper.extract_results (url, schema_def, extracted)
                VALUES (%s, %s, %s)
                RETURNING id, created_at
                """,
                (EXTRACT_URL, json.dumps(EXTRACT_SCHEMA), json.dumps(extracted)),
            )
            row_id, created_at = cur.fetchone()
        conn.commit()
        _ok(f"Persisted to scraper.extract_results — id={row_id}, created_at={created_at}")

        # Verify and display
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT id, url, extracted FROM scraper.extract_results WHERE id = %s",
                (row_id,),
            )
            row = cur.fetchone()

        db_extracted = row["extracted"]
        if isinstance(db_extracted, str):
            db_extracted = json.loads(db_extracted)

        _ok(f"Verification read: id={row['id']}, url={row['url']}")
        print()
        _info("Extracted records (from DB query):")
        items = db_extracted if isinstance(db_extracted, list) else [db_extracted]
        for i, item in enumerate(items[:20], 1):
            if isinstance(item, dict):
                title   = item.get("book_title", "?")
                price   = item.get("price", "?")
                stars   = item.get("star_rating", "?")
                avail   = item.get("availability", "?")
                print(f"    {i:>2}.  {title[:50]:<50}  {price:<10}  {stars:<6}  {avail}")
            else:
                print(f"    {i:>2}.  {item}")

        _results["step5"] = {"pass": True, "row_id": row_id, "item_count": len(items)}

    except Exception as exc:
        _record_failure("step5", exc)


# ──────────────────────────────────────────────────────────────────────────────
# Step 6 — Final Validation Report
# ──────────────────────────────────────────────────────────────────────────────

def _print_final_report(partial: bool = False) -> None:
    total_elapsed = time.time() - _suite_start

    _hdr("Step 6 — Final Validation Report")

    if partial:
        _info("(Partial report — test suite halted early due to failure)")

    STEP_LABELS = {
        "step1": "DB Pre-Test Connection & Schema",
        "step2": "Scrape — single URL",
        "step3": "Map — site structure",
        "step4": "Crawl — 10-page multi-page",
        "step5": "Extract — structured LLM",
    }

    print()
    print("  Feature Test Results:")
    print(f"  {'Test':<42} {'Status':<8}  Detail")
    print("  " + "-" * 72)
    all_pass = True
    for key, label in STEP_LABELS.items():
        r = _results.get(key)
        if r is None:
            status = "SKIP"
            detail = "Not reached"
        elif r["pass"]:
            status = "PASS"
            detail = str({k: v for k, v in r.items() if k != "pass" and k != "baseline"})[:60]
        else:
            status = "FAIL"
            detail = str(r.get("error", ""))[:60]
            all_pass = False
        marker = "✓" if status == "PASS" else ("!" if status == "FAIL" else "-")
        print(f"  [{marker}] {label:<40} {status:<8}  {detail}")

    # Row count deltas
    baseline = (_results.get("step1") or {}).get("baseline", {})
    if baseline and _db_conn and not _db_conn.closed:
        print()
        print("  Row Counts (pre-test → post-test):")
        print(f"  {'Table':<42} {'Before':>7}  {'After':>7}  {'Delta':>7}")
        print("  " + "-" * 65)
        with _db_conn.cursor() as cur:
            post = _row_counts(cur, SCRAPER_TABLES)
        for t in SCRAPER_TABLES:
            pre  = baseline.get(t, -1)
            aft  = post.get(t, -1)
            dlt  = (aft - pre) if pre >= 0 and aft >= 0 else "N/A"
            print(f"  {t:<42} {str(pre):>7}  {str(aft):>7}  {str(dlt):>7}")

    print()
    print(f"  Total elapsed time: {total_elapsed:.1f}s")
    print()

    if all_pass and not partial:
        _ok("ALL TESTS PASSED — Firecrawl features operational and persisting to Postgres.")
    else:
        _fail("One or more tests FAILED. Review errors above.")


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main():
    print()
    print("  Firecrawl Feature Validation Suite")
    print(f"  Started: {_now_utc().isoformat()}")

    step0_environment()
    baseline = step1_db_pre_test()
    step2_scrape()
    step3_map()
    step4_crawl()
    step5_extract()
    _print_final_report()

    if _db_conn and not _db_conn.closed:
        _db_conn.close()


if __name__ == "__main__":
    main()
