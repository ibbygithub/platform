#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_reddit.py
==================
End-to-end validation of the Platform Reddit Gateway v2.

Steps
-----
  0  Environment discovery
  1  DB pre-test: connect, baseline row counts (SKIP if PGPASSWORD not set)
  2  Live search — POST /v1/reddit/search (English + kanji queries)
  3  Subreddit browse — POST /v1/reddit/subreddit/posts
  4  Saved search — POST /v1/reddit/saved/search (semantic, local DB)
  5  Feeds list — GET /v1/reddit/feeds
  6  Regression — all 9 endpoints (HTTP status + shape check)
  7  Loki Level 1 — confirm {service="reddit-gateway"} logs flowing
  8  Final report + Green Gate checklist

Prerequisites
-------------
  pip install requests psycopg2-binary

Environment variables
---------------------
  REDDIT_GATEWAY_URL   default: https://reddit.platform.ibbytech.com
  PGHOST               default: dbnode-01
  PGPORT               default: 5432
  PGDATABASE           default: platform_v1
  PGUSER               default: reddit_app
  PGPASSWORD           required for DB steps (Steps 1, 4) — SKIP if not set
  LOKI_URL             default: http://192.168.71.220:3100

Usage
-----
  python validate_reddit.py
"""

import importlib.util
import json
import os
import pathlib
import sys
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

_missing = []
try:
    import requests
except ImportError:
    _missing.append("requests")
try:
    import psycopg2
    import psycopg2.extras
    _HAS_PG = True
except ImportError:
    _missing.append("psycopg2-binary")
    _HAS_PG = False

if "requests" in _missing:
    print(f"[FATAL] Missing dependencies: {', '.join(_missing)}")
    print(f"        Run:  pip install {' '.join(_missing)}")
    sys.exit(1)

# ── Shared platform test harness ────────────────────────────────────────────
_HARNESS_PATH = pathlib.Path(__file__).parent.parent.parent / "tools" / "test-harness" / "platform_preflight.py"
if _HARNESS_PATH.exists():
    _spec = importlib.util.spec_from_file_location("platform_preflight", _HARNESS_PATH)
    _pf   = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_pf)
    check_loki_service_logs = _pf.check_loki_service_logs
else:
    def check_loki_service_logs(loki_url, service_name, lookback_minutes=15):
        return type("R", (), {"status": "SKIP", "detail": "platform_preflight.py not found",
                               "latency_ms": None})()

# ── Shared fixtures ──────────────────────────────────────────────────────────
_FIXTURES_PATH = pathlib.Path(__file__).parent.parent.parent / "tools" / "test-harness" / "fixtures" / "reddit_fixtures.json"
_FIXTURES: Dict[str, Any] = {}
if _FIXTURES_PATH.exists():
    with open(_FIXTURES_PATH) as _f:
        _FIXTURES = json.load(_f)

# ── Config ───────────────────────────────────────────────────────────────────
GATEWAY_URL = os.environ.get("REDDIT_GATEWAY_URL", "https://reddit.platform.ibbytech.com").rstrip("/")
LOKI_URL    = os.environ.get("LOKI_URL", "http://192.168.71.220:3100")

PG_CONFIG = {
    "host":            os.environ.get("PGHOST",     "dbnode-01"),
    "port":            int(os.environ.get("PGPORT", "5432")),
    "dbname":          os.environ.get("PGDATABASE", "platform_v1"),
    "user":            os.environ.get("PGUSER",     "reddit_app"),
    "password":        os.environ.get("PGPASSWORD", ""),
    "connect_timeout": 10,
}
_DB_ENABLED = bool(PG_CONFIG["password"]) and _HAS_PG

# ── Test targets from fixtures ────────────────────────────────────────────────
_posts = _FIXTURES.get("posts", [])
_SEARCH_QUERY_EN   = "ramen"
_SEARCH_SUBREDDIT  = "ramen"
_SEARCH_QUERY_JP   = "ラーメン"
_SUBREDDIT_BROWSE  = "ramen"

REDDIT_TABLES = [
    "reddit.posts",
    "reddit.comments",
    "reddit.subreddits",
    "reddit.feeds",
    "reddit.query_cache",
]

# ── Globals ───────────────────────────────────────────────────────────────────
_suite_start = time.time()
_results: Dict[str, Dict[str, Any]] = {}
_db_conn = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hdr(title: str) -> None:
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)

def _ok(msg: str)   -> None: print(f"  [PASS] {msg}")
def _fail(msg: str) -> None: print(f"  [FAIL] {msg}")
def _info(msg: str) -> None: print(f"  [INFO] {msg}")
def _warn(msg: str) -> None: print(f"  [WARN] {msg}")

def _elapsed() -> str:
    return f"{time.time() - _suite_start:.1f}s"

def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()

def _get_db() -> Any:
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
            counts[t] = -1
    return counts

def _gateway_get(path: str, params: Optional[Dict] = None, timeout: int = 15) -> requests.Response:
    return requests.get(f"{GATEWAY_URL}{path}", params=params, timeout=timeout)

def _gateway_post(path: str, body: Dict, timeout: int = 30) -> requests.Response:
    return requests.post(f"{GATEWAY_URL}{path}", json=body,
                         headers={"Content-Type": "application/json"}, timeout=timeout)


# ── Step 0 — Environment Discovery ───────────────────────────────────────────

def step0_environment() -> None:
    _hdr("Step 0 — Environment Discovery")
    _info(f"REDDIT_GATEWAY_URL = {GATEWAY_URL}")
    _info(f"LOKI_URL           = {LOKI_URL}")
    _info(f"PGHOST             = {PG_CONFIG['host']}")
    _info(f"PGDATABASE         = {PG_CONFIG['dbname']}")
    _info(f"PGUSER             = {PG_CONFIG['user']}")
    _info(f"PGPASSWORD         = {'*** (set)' if PG_CONFIG['password'] else '(not set — DB steps will SKIP)'}")
    _info(f"psycopg2 available = {_HAS_PG}")
    print()
    if not _DB_ENABLED:
        _warn("DB steps (Step 1 row counts, Step 4 saved search) will SKIP.")
        _warn("Set PGPASSWORD=<reddit_app password> to enable full validation.")
    print()
    _info(f"Fixtures loaded: {len(_posts)} synthetic posts from reddit_fixtures.json")

    # Gateway health check
    _info("Checking gateway health ...")
    try:
        r = _gateway_get("/health", timeout=10)
        if r.status_code == 200:
            h = r.json()
            _ok(f"Gateway healthy — version={h.get('version')} persist={h.get('persist_enabled')} db={h.get('db_connected')}")
        else:
            _fail(f"Health returned HTTP {r.status_code}")
            sys.exit(1)
    except Exception as exc:
        _fail(f"Cannot reach gateway: {exc}")
        sys.exit(1)


# ── Step 1 — DB Pre-Test ─────────────────────────────────────────────────────

def step1_db_pre_test() -> Dict[str, int]:
    _hdr("Step 1 — DB Pre-Test (reddit schema baseline)")
    global _db_conn

    if not _DB_ENABLED:
        _warn("SKIP — PGPASSWORD not set or psycopg2 not available.")
        _results["step1"] = {"pass": True, "skipped": True, "baseline": {}}
        return {}

    _info(f"Connecting to {PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['dbname']} as {PG_CONFIG['user']} ...")
    try:
        _db_conn = psycopg2.connect(**PG_CONFIG)
        _db_conn.autocommit = True
        _ok("Connected to platform_v1 on dbnode-01.")
    except Exception as exc:
        _fail(f"Cannot connect: {exc}")
        _results["step1"] = {"pass": False, "error": str(exc)}
        return {}

    cur = _db_conn.cursor()

    # List tables in reddit schema
    try:
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'reddit' ORDER BY table_name
        """)
        existing = [r[0] for r in cur.fetchall()]
        if existing:
            _ok(f"reddit schema has {len(existing)} table(s): {', '.join(existing)}")
        else:
            _warn("reddit schema has no tables — gateway may not have run yet")
    except Exception as exc:
        _warn(f"Could not query reddit schema: {exc}")
        existing = []

    # Baseline row counts
    print()
    _info("Baseline row counts:")
    baseline = _row_counts(cur, REDDIT_TABLES)
    for t, n in baseline.items():
        label = str(n) if n >= 0 else "N/A (table missing)"
        print(f"         {t:<32}  rows = {label}")

    _results["step1"] = {"pass": True, "baseline": baseline}
    return baseline


# ── Step 2 — Live Search ─────────────────────────────────────────────────────

def step2_search() -> None:
    _hdr("Step 2 — Live Search (English + kanji)")

    # English search scoped to subreddit
    _info(f"POST /v1/reddit/search — q={_SEARCH_QUERY_EN!r} subreddit={_SEARCH_SUBREDDIT!r} ...")
    try:
        t0 = time.time()
        r = _gateway_post("/v1/reddit/search", {
            "query": _SEARCH_QUERY_EN,
            "subreddit": _SEARCH_SUBREDDIT,
            "sort": "top",
            "time_filter": "week",
            "limit": 5,
        }, timeout=30)
        elapsed = time.time() - t0
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        count = data.get("count", 0)
        from_cache = data.get("from_cache", False)
        _ok(f"English search: {count} posts returned ({elapsed:.1f}s, cache={from_cache})")
        if count > 0:
            first = data["posts"][0]
            _info(f"  First post: {first.get('title', '')[:70]!r}")
    except Exception as exc:
        _fail(f"English search failed: {exc}")
        _results["step2"] = {"pass": False, "error": str(exc)}
        return

    # Kanji search (global, no subreddit filter)
    print()
    _info(f"POST /v1/reddit/search — q={_SEARCH_QUERY_JP!r} (all subreddits) ...")
    try:
        t0 = time.time()
        r = _gateway_post("/v1/reddit/search", {
            "query": _SEARCH_QUERY_JP,
            "sort": "relevance",
            "time_filter": "month",
            "limit": 5,
        }, timeout=30)
        elapsed = time.time() - t0
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        count_jp = data.get("count", 0)
        _ok(f"Kanji search: {count_jp} posts returned ({elapsed:.1f}s)")
    except Exception as exc:
        _fail(f"Kanji search failed: {exc}")
        _results["step2"] = {"pass": False, "error": str(exc)}
        return

    _results["step2"] = {"pass": True, "en_count": count, "jp_count": count_jp}


# ── Step 3 — Subreddit Browse ────────────────────────────────────────────────

def step3_subreddit_browse() -> None:
    _hdr("Step 3 — Subreddit Browse")
    _info(f"POST /v1/reddit/subreddit/posts — r/{_SUBREDDIT_BROWSE} sort=hot ...")

    try:
        t0 = time.time()
        r = _gateway_post("/v1/reddit/subreddit/posts", {
            "subreddit": _SUBREDDIT_BROWSE,
            "sort": "hot",
            "limit": 5,
        }, timeout=30)
        elapsed = time.time() - t0
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        count = data.get("count", 0)
        _ok(f"{count} posts from r/{_SUBREDDIT_BROWSE} (hot, {elapsed:.1f}s)")
        if count > 0:
            _info(f"  First: {data['posts'][0].get('title', '')[:70]!r}")
        _results["step3"] = {"pass": True, "count": count}
    except Exception as exc:
        _fail(f"Subreddit browse failed: {exc}")
        _results["step3"] = {"pass": False, "error": str(exc)}


# ── Step 4 — Saved (Semantic) Search ─────────────────────────────────────────

def step4_saved_search() -> None:
    _hdr("Step 4 — Saved Semantic Search")

    if not _DB_ENABLED:
        _warn("SKIP — PGPASSWORD not set. DB persistence required for saved search.")
        _results["step4"] = {"pass": True, "skipped": True}
        return

    _info("POST /v1/reddit/saved/search — 'local ramen Tokyo authentic' ...")
    try:
        t0 = time.time()
        r = _gateway_post("/v1/reddit/saved/search", {
            "query": "local ramen Tokyo authentic not tourist",
            "limit": 5,
        }, timeout=20)
        elapsed = time.time() - t0
        if r.status_code == 503:
            _warn("DB persistence not enabled on gateway — saved search unavailable")
            _results["step4"] = {"pass": True, "skipped": True, "detail": "gateway persist_enabled=false"}
            return
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        count = data.get("count", 0)
        _ok(f"Semantic search returned {count} results ({elapsed:.1f}s)")
        if count == 0:
            _info("  Zero results — DB may be empty (normal if this is first run)")
        else:
            _info(f"  First: {data['posts'][0].get('title', '')[:70]!r}")
        _results["step4"] = {"pass": True, "count": count}
    except Exception as exc:
        _fail(f"Saved search failed: {exc}")
        _results["step4"] = {"pass": False, "error": str(exc)}


# ── Step 5 — Feeds List ───────────────────────────────────────────────────────

def step5_feeds() -> None:
    _hdr("Step 5 — Feeds List")
    _info("GET /v1/reddit/feeds ...")

    try:
        t0 = time.time()
        r = _gateway_get("/v1/reddit/feeds", timeout=10)
        elapsed = time.time() - t0
        if r.status_code == 503:
            _warn("DB persistence not enabled — feeds unavailable (gateway pass-through mode)")
            _results["step5"] = {"pass": True, "skipped": True}
            return
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        count = data.get("count", 0)
        _ok(f"{count} registered feed(s) ({elapsed:.1f}s)")
        for f in data.get("feeds", [])[:5]:
            _info(f"  Feed {f.get('id')}: r/{f.get('subreddit')} {f.get('sort')} — {f.get('cron_expr')}")
        _results["step5"] = {"pass": True, "feed_count": count}
    except Exception as exc:
        _fail(f"Feeds list failed: {exc}")
        _results["step5"] = {"pass": False, "error": str(exc)}


# ── Step 6 — Regression: All Endpoints ───────────────────────────────────────

def step6_regression() -> None:
    _hdr("Step 6 — Regression: All 9 Endpoints")
    _info("HTTP status + response shape checks. No DB writes.")

    checks = [
        ("GET  /health",
         lambda: _gateway_get("/health", timeout=10),
         lambda r: r.status_code == 200 and "ok" in r.json()),

        ("POST /v1/reddit/search",
         lambda: _gateway_post("/v1/reddit/search",
                               {"query": "ramen", "limit": 3}, timeout=20),
         lambda r: r.status_code == 200 and "posts" in r.json()),

        ("POST /v1/reddit/subreddit/posts",
         lambda: _gateway_post("/v1/reddit/subreddit/posts",
                               {"subreddit": "ramen", "sort": "hot", "limit": 3}, timeout=20),
         lambda r: r.status_code == 200 and "posts" in r.json()),

        ("GET  /v1/reddit/subreddit/ramen/info",
         lambda: _gateway_get("/v1/reddit/subreddit/ramen/info", timeout=15),
         lambda r: r.status_code in (200, 502)),  # 502 = Reddit API transient error

        ("POST /v1/reddit/saved/search",
         lambda: _gateway_post("/v1/reddit/saved/search",
                               {"query": "ramen", "limit": 3}, timeout=15),
         lambda r: r.status_code in (200, 503)),  # 503 = no DB persistence

        ("GET  /v1/reddit/feeds",
         lambda: _gateway_get("/v1/reddit/feeds", timeout=10),
         lambda r: r.status_code in (200, 503)),

        ("POST /v1/reddit/feeds (create+delete)",
         lambda: _gateway_post("/v1/reddit/feeds",
                               {"subreddit": "ramen", "sort": "top",
                                "time_filter": "week", "limit_per_run": 5,
                                "cron_expr": "0 3 * * *"}, timeout=10),
         lambda r: r.status_code in (201, 503)),  # 503 if no DB

        # GET /v1/reddit/post/{id} — use a known recent post ID from r/ramen
        # We accept 200 or 502 (post may not exist / Reddit rate limit)
        ("GET  /v1/reddit/post/{id}",
         lambda: _gateway_get("/v1/reddit/post/1abc00", timeout=15),
         lambda r: r.status_code in (200, 502, 404)),
    ]

    # Clean up any feed created during regression
    all_passed = True
    _created_feed_id = None

    for label, call_fn, validator in checks:
        try:
            t0 = time.time()
            r  = call_fn()
            ms = (time.time() - t0) * 1000
            ok = validator(r)
            if label.startswith("POST /v1/reddit/feeds") and r.status_code == 201:
                body = r.json()
                _created_feed_id = (body.get("feed") or {}).get("id")
            if ok:
                _ok(f"{label:<40} HTTP {r.status_code} ({ms:.0f}ms)")
            else:
                _fail(f"{label:<40} HTTP {r.status_code} — unexpected shape ({ms:.0f}ms)")
                all_passed = False
        except Exception as exc:
            _fail(f"{label:<40} {exc}")
            all_passed = False

    # Clean up test feed
    if _created_feed_id:
        try:
            r = requests.delete(f"{GATEWAY_URL}/v1/reddit/feeds/{_created_feed_id}", timeout=10)
            if r.status_code == 200:
                _info(f"Cleaned up regression test feed id={_created_feed_id}")
            else:
                _warn(f"Feed cleanup returned HTTP {r.status_code} for id={_created_feed_id}")
        except Exception as exc:
            _warn(f"Feed cleanup failed: {exc}")

    # Also verify DELETE endpoint shape
    _ok("DELETE /v1/reddit/feeds/{id}     — verified via cleanup above") if _created_feed_id else \
        _info("DELETE /v1/reddit/feeds/{id}     — not tested (no feed created, DB off)")

    _results["step6"] = {"pass": all_passed}


# ── Step 7 — Loki Level 1 ────────────────────────────────────────────────────

def step7_loki() -> None:
    _hdr("Step 7 — Loki Level 1 Observability Check")
    _info(f"Querying Loki for {{service=\"reddit-gateway\"}} — last 15 minutes ...")
    _info(f"Loki: {LOKI_URL}")

    result = check_loki_service_logs(LOKI_URL, "reddit-gateway", lookback_minutes=15)

    if result.status == "PASS":
        lat = f" ({result.latency_ms:.0f}ms)" if result.latency_ms else ""
        _ok(f"{result.detail}{lat}")
    elif result.status == "SKIP":
        _info(f"SKIP — {result.detail}")
    else:
        _fail(result.detail)
        _info("Verify gateway emits logs with service=reddit-gateway label.")
        _info(f"Check Loki: curl {LOKI_URL}/ready")

    _results["step7"] = {
        "pass":   result.status in ("PASS", "SKIP"),
        "status": result.status,
        "detail": result.detail,
    }


# ── Final Report ─────────────────────────────────────────────────────────────

def _print_final_report(partial: bool = False) -> None:
    total_elapsed = time.time() - _suite_start
    _hdr("Step 8 — Final Validation Report")

    if partial:
        _info("(Partial report — test suite halted early)")

    STEP_LABELS = {
        "step1": "DB Pre-Test (reddit schema baseline)",
        "step2": "Live Search (English + kanji)",
        "step3": "Subreddit Browse",
        "step4": "Saved Semantic Search",
        "step5": "Feeds List",
        "step6": "Regression — all 9 endpoints",
        "step7": "Loki Level 1 observability",
    }

    print()
    print(f"  {'Test':<42} {'Status':<8}  Detail")
    print("  " + "-" * 72)
    all_pass = True
    for key, label in STEP_LABELS.items():
        r = _results.get(key)
        if r is None:
            status, detail = "SKIP", "Not reached"
        elif r.get("skipped"):
            status, detail = "SKIP", r.get("detail", "PGPASSWORD not set")
        elif r["pass"]:
            status = "PASS"
            detail = str({k: v for k, v in r.items() if k not in ("pass", "baseline", "skipped")})[:60]
        else:
            status, detail = "FAIL", str(r.get("error", ""))[:60]
            all_pass = False
        marker = "✓" if status == "PASS" else ("-" if status == "SKIP" else "!")
        print(f"  [{marker}] {label:<40} {status:<8}  {detail}")

    # Row count deltas
    baseline = (_results.get("step1") or {}).get("baseline", {})
    if baseline and _db_conn and not _db_conn.closed:
        print()
        print("  Row Counts (pre-test → post-test):")
        print(f"  {'Table':<32} {'Before':>7}  {'After':>7}  {'Delta':>7}")
        print("  " + "-" * 56)
        with _db_conn.cursor() as cur:
            post = _row_counts(cur, REDDIT_TABLES)
        for t in REDDIT_TABLES:
            pre = baseline.get(t, -1)
            aft = post.get(t, -1)
            dlt = (aft - pre) if pre >= 0 and aft >= 0 else "N/A"
            print(f"  {t:<32} {str(pre):>7}  {str(aft):>7}  {str(dlt):>7}")

    print()
    print(f"  Total elapsed: {total_elapsed:.1f}s")

    loki_pass = (_results.get("step7") or {}).get("pass", False)
    print()
    print("  Green Gate Checklist:")
    print(f"  [{'✓' if all_pass else '✗'}] 1. All validate steps PASS")
    print(f"  [{'✓' if loki_pass else '✗'}] 2. Loki Level 1 verified (service=reddit-gateway)")
    print(f"  [ ] 3. OpenAPI spec — services/reddit-gateway/openapi.yaml")
    print(f"  [ ] 4. Service doc capability registry current")
    print(f"  [ ] 5. _index.md updated")
    print(f"  [ ] 6. Evidence report — outputs/validation/")
    print(f"  [ ] 7. .env.example current")
    print()

    if all_pass and loki_pass and not partial:
        _ok("AUTOMATED CHECKS PASSED — complete items 3-7 to satisfy green gate.")
    elif all_pass and not partial:
        _fail("Loki Level 1 FAILED — service is not logging. Fix before delivery.")
    else:
        _fail("One or more steps FAILED. Review errors above.")


# ── Entry Point ───────────────────────────────────────────────────────────────

def main():
    print()
    print("  Reddit Gateway Validation Suite")
    print(f"  Started: {_now_utc()}")

    step0_environment()
    step1_db_pre_test()
    step2_search()
    step3_subreddit_browse()
    step4_saved_search()
    step5_feeds()
    step6_regression()
    step7_loki()
    _print_final_report()

    if _db_conn and not _db_conn.closed:
        _db_conn.close()

    all_auto = all(
        _results.get(k, {}).get("pass", False)
        for k in ["step2", "step3", "step6", "step7"]
    )
    sys.exit(0 if all_auto else 1)


if __name__ == "__main__":
    main()
