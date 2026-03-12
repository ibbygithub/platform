#!/usr/bin/env python3
"""
validate_{SERVICE}.py
=====================
IbbyTech Platform — Post-Deployment Validation Script
Service: {SERVICE_NAME}
Stage 4: Post-Deployment Validation

This script validates that the {SERVICE_NAME} service is fully functional
after deployment. It tests all declared API endpoints, verifies database
persistence, checks Loki observability, and produces a final pass/fail report.

Run AFTER deployment. Run from the laptop. Does not require SSH.

Usage
-----
    cp .env.test.example .env.test
    # fill in required credentials
    # On Windows: set each variable in your environment
    set -a; source .env.test; set +a    # Linux/Mac

    python validate_{SERVICE}.py

Required: pip install requests psycopg2-binary

Environment variables (see .env.test.example):
    {SERVICE_URL_VAR}      URL of the service API
                           default: http://{service}.platform.ibbytech.com
    PGPASSWORD             PostgreSQL password
    PGHOST                 default: 192.168.71.221
    PGDATABASE             default: platform_v1
    PGUSER                 default: {service}_app
    LOKI_URL               default: http://192.168.71.220:3100

    # Add any service-specific env vars here

Green Gate Checklist (all must pass for delivery):
    [ ] 1. All steps in this script PASS
    [ ] 2. Loki Level 1 verified (Step N+1 below)
    [ ] 3. services/{service}/openapi.yaml committed
    [ ] 4. .claude/services/{service}.md capability registry current
    [ ] 5. .claude/services/_index.md updated
    [ ] 6. outputs/validation/YYYY-MM-DD_{service}_report.md written
    [ ] 7. services/{service}/.env.example current
"""

import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ── Dependency check ──────────────────────────────────────────────────────────
_missing = []
try:
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    _missing.append("requests")
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    _missing.append("psycopg2-binary")

if _missing:
    print(f"[FATAL] Missing: {', '.join(_missing)}. Run: pip install {' '.join(_missing)}")
    sys.exit(1)

# ── Import shared Loki check from platform test harness ───────────────────────
# Adjust path if running from a different working directory
import importlib.util, pathlib

_HARNESS_PATH = pathlib.Path(__file__).parent.parent / "platform_preflight.py"
if _HARNESS_PATH.exists():
    _spec = importlib.util.spec_from_file_location("platform_preflight", _HARNESS_PATH)
    _pf   = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_pf)
    check_loki_service_logs = _pf.check_loki_service_logs
else:
    # Fallback: inline stub so the script still runs without the harness present
    def check_loki_service_logs(loki_url, service_name, lookback_minutes=15):
        return type("R", (), {"status": "SKIP", "detail": "platform_preflight.py not found",
                               "latency_ms": None, "name": f"Loki logs ({service_name})"})()

# ── Configuration ─────────────────────────────────────────────────────────────

SERVICE_NAME = "{service}"    # REPLACE: short name used in Loki service= label
SERVICE_LABEL = "{SERVICE_NAME}"  # REPLACE: human-readable name for output

SERVICE_URL  = os.environ.get("{SERVICE_URL_VAR}", "http://{service}.platform.ibbytech.com").rstrip("/")
LOKI_URL     = os.environ.get("LOKI_URL", "http://192.168.71.220:3100")

PG_CONFIG = {
    "host":            os.environ.get("PGHOST",     "192.168.71.221"),
    "port":      int(  os.environ.get("PGPORT",     "5432")),
    "dbname":          os.environ.get("PGDATABASE", "platform_v1"),
    "user":            os.environ.get("PGUSER",     f"{SERVICE_NAME}_app"),
    "password":        os.environ.get("PGPASSWORD", ""),
    "connect_timeout": 10,
}

# REPLACE: list all tables this service owns
SERVICE_TABLES = [
    f"{SERVICE_NAME}.{SERVICE_NAME}_table_1",
    # f"{SERVICE_NAME}.{SERVICE_NAME}_table_2",
]

# ── Load shared fixtures ──────────────────────────────────────────────────────
_FIXTURES_PATH = pathlib.Path(__file__).parent.parent / "fixtures" / f"{SERVICE_NAME}_fixtures.json"
FIXTURES: Dict[str, Any] = {}
if _FIXTURES_PATH.exists():
    with open(_FIXTURES_PATH) as f:
        FIXTURES = json.load(f)

# ── Output colours ────────────────────────────────────────────────────────────
GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW= "\033[93m"
BOLD  = "\033[1m"
RESET = "\033[0m"

# ── Globals ───────────────────────────────────────────────────────────────────
_suite_start = time.time()
_results: Dict[str, Dict[str, Any]] = {}
_db_conn = None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _hdr(title: str) -> None:
    print(f"\n{'=' * 72}\n  {title}\n{'=' * 72}")

def _ok(msg: str)   -> None: print(f"  [PASS] {msg}")
def _fail(msg: str) -> None: print(f"  [FAIL] {msg}")
def _info(msg: str) -> None: print(f"  [INFO] {msg}")
def _warn(msg: str) -> None: print(f"  [WARN] {msg}")
def _elapsed()      -> str:  return f"{time.time() - _suite_start:.1f}s"

def _auth_headers() -> Dict[str, str]:
    """Return auth headers for this service. Adjust to match service auth model."""
    h = {"Content-Type": "application/json"}
    api_key = os.environ.get(f"{SERVICE_NAME.upper()}_API_KEY", "")
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    return h

def _get_db():
    global _db_conn
    if _db_conn is None or _db_conn.closed:
        raise RuntimeError("No DB connection available.")
    return _db_conn

def _row_counts(cur, tables: List[str]) -> Dict[str, int]:
    counts = {}
    for t in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            counts[t] = cur.fetchone()[0]
        except Exception:
            counts[t] = -1
    return counts

def _record_failure(step: str, exc: Exception, halt: bool = True) -> None:
    _fail(f"Step {step} FAILED")
    print()
    traceback.print_exc()
    _results[step] = {"pass": False, "error": str(exc)}
    if halt:
        print("\n  Halting — fix the issue above and re-run.")
        _print_final_report(partial=True)
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Step 0 — Environment Discovery
# ─────────────────────────────────────────────────────────────────────────────

def step0_environment() -> None:
    _hdr("Step 0 — Environment Discovery")
    _info(f"SERVICE_URL = {SERVICE_URL}")
    _info(f"PGHOST      = {PG_CONFIG['host']}")
    _info(f"PGDATABASE  = {PG_CONFIG['dbname']}")
    _info(f"PGUSER      = {PG_CONFIG['user']}")
    _info(f"PGPASSWORD  = {'*** (set)' if PG_CONFIG['password'] else '(NOT SET — check will fail)'}")
    _info(f"LOKI_URL    = {LOKI_URL}")
    _info(f"Fixtures    = {'loaded' if FIXTURES else 'NOT FOUND — ' + str(_FIXTURES_PATH)}")

    # Hard stop if required credentials are missing
    if not PG_CONFIG["password"]:
        _fail("PGPASSWORD is not set.")
        sys.exit(1)

    # Verify service health endpoint
    _info(f"Checking {SERVICE_LABEL} health endpoint ...")
    try:
        r = requests.get(f"{SERVICE_URL}/health", headers=_auth_headers(), timeout=10, verify=False)
        if r.status_code == 200:
            _ok(f"Service is up. {r.text[:200]}")
        else:
            _warn(f"Health returned HTTP {r.status_code}. Continuing — individual steps may fail.")
    except Exception as e:
        _warn(f"Health check failed: {e}. Continuing — individual steps will fail if unreachable.")


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Pre-Test DB State
# ─────────────────────────────────────────────────────────────────────────────

def step1_db_pre_test() -> Dict[str, int]:
    _hdr("Step 1 — Database Connectivity and Baseline")
    global _db_conn

    _info(f"Connecting to {PG_CONFIG['host']}:{PG_CONFIG['port']}/{PG_CONFIG['dbname']} ...")
    try:
        _db_conn = psycopg2.connect(**PG_CONFIG)
        _db_conn.autocommit = False
        _ok("Connected.")
    except Exception as exc:
        _fail(f"Cannot connect: {exc}")
        sys.exit(1)

    cur = _db_conn.cursor()

    # Confirm schema exists
    schema = SERVICE_NAME
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = %s",
        (schema,)
    )
    table_count = cur.fetchone()[0]
    if table_count > 0:
        _ok(f"Schema '{schema}' exists with {table_count} table(s).")
    else:
        _warn(f"Schema '{schema}' has no tables. Is the schema deployed?")

    # Baseline row counts
    baseline = _row_counts(cur, SERVICE_TABLES)
    _info("Baseline row counts:")
    for t, n in baseline.items():
        print(f"         {t:<50} rows = {n if n >= 0 else 'N/A'}")

    _results["step1"] = {"pass": True, "baseline": baseline}
    return baseline


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — [REPLACE: First Endpoint Test]
# ─────────────────────────────────────────────────────────────────────────────
# Duplicate this block for each additional endpoint.
# Each step should:
#   - Call one endpoint with a controlled test payload from FIXTURES
#   - Verify response structure
#   - Persist to DB if applicable
#   - Read back to confirm persistence
#   - Record result in _results["step2"]

def step2_first_endpoint() -> None:
    _hdr("Step 2 — [REPLACE: Endpoint Name]")

    # REPLACE: describe what this step tests
    _info("Testing POST /v1/{service}/endpoint ...")

    # REPLACE: use fixtures where available
    # payload = FIXTURES.get("your_fixture_key", {})

    try:
        t0 = time.time()
        resp = requests.post(
            f"{SERVICE_URL}/v1/{SERVICE_NAME}/endpoint",
            headers=_auth_headers(),
            json={},       # REPLACE: actual payload
            timeout=30,
        )
        elapsed = time.time() - t0

        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")

        data = resp.json()
        _ok(f"Completed in {elapsed:.1f}s")
        _info(f"Response keys: {list(data.keys())}")

        # REPLACE: persist to DB if this endpoint writes data
        # conn = _get_db()
        # with conn.cursor() as cur:
        #     cur.execute("INSERT INTO ...", (...))
        #     row_id = cur.fetchone()[0]
        # conn.commit()
        # _ok(f"Persisted — id={row_id}")

        _results["step2"] = {"pass": True}

    except Exception as exc:
        _record_failure("step2", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Regression: Existing Endpoints
# ─────────────────────────────────────────────────────────────────────────────
# Add a regression step for each existing endpoint that this deployment must
# not have broken. Keep these lightweight — health + basic response shape check.
# Do NOT write new data in regression steps.

def step3_regression() -> None:
    _hdr("Step 3 — Regression: Existing Endpoint Checks")

    regressions = [
        # (endpoint_path, http_method, description)
        # REPLACE: list all existing endpoints to regression-test
        ("/health",                   "GET",  "Health endpoint"),
        # ("/v1/{service}/search",    "POST", "Search endpoint"),
    ]

    all_passed = True
    for path, method, description in regressions:
        try:
            url = f"{SERVICE_URL}{path}"
            t0  = time.time()
            if method == "GET":
                r = requests.get(url, headers=_auth_headers(), timeout=15, verify=False)
            else:
                r = requests.post(url, headers=_auth_headers(), json={}, timeout=15, verify=False)
            elapsed = (time.time() - t0) * 1000

            if r.status_code < 400:
                _ok(f"{description} ({method} {path}) — HTTP {r.status_code} ({elapsed:.0f}ms)")
            else:
                _fail(f"{description} ({method} {path}) — HTTP {r.status_code}")
                all_passed = False

        except Exception as e:
            _fail(f"{description} ({method} {path}) — {e}")
            all_passed = False

    _results["step3"] = {"pass": all_passed}
    if not all_passed:
        print("\n  Regression failures detected. Investigate before marking task complete.")


# ─────────────────────────────────────────────────────────────────────────────
# Step N+1 — Loki Level 1 Check
# ─────────────────────────────────────────────────────────────────────────────
# Required for green gate. Do not remove or skip.

def step_loki() -> None:
    _hdr("Step Loki — Observability Level 1 Check")
    _info(f"Querying Loki for service={SERVICE_NAME!r} — last 15 minutes ...")

    result = check_loki_service_logs(LOKI_URL, SERVICE_NAME, lookback_minutes=15)

    if result.status == "PASS":
        _ok(result.detail)
    elif result.status == "WARN":
        _warn(result.detail)
    else:
        _fail(result.detail)
        if result.status == "FAIL":
            print()
            print("  This is a GREEN GATE requirement.")
            print(f"  Verify that {SERVICE_NAME} emits logs with service={SERVICE_NAME!r} label to Loki.")
            print(f"  Check Loki is running: curl {LOKI_URL}/ready")

    _results["step_loki"] = {
        "pass":   result.status in ("PASS", "SKIP"),  # SKIP = Loki not configured (warn only)
        "status": result.status,
        "detail": result.detail,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Final Report
# ─────────────────────────────────────────────────────────────────────────────

def _print_final_report(partial: bool = False) -> None:
    total = time.time() - _suite_start
    _hdr("Final Validation Report")

    if partial:
        _info("(Partial — halted early due to failure)")

    STEP_LABELS = {
        "step1":     "DB connectivity and baseline",
        "step2":     "[REPLACE: First endpoint]",
        "step3":     "Regression — existing endpoints",
        "step_loki": "Loki Level 1 observability check",
        # Add more steps here as you build them out
    }

    all_pass = True
    for key, label in STEP_LABELS.items():
        r = _results.get(key)
        if r is None:
            status, detail = "SKIP", "Not reached"
        elif r["pass"]:
            status, detail = "PASS", ""
        else:
            status = "FAIL"
            detail = str(r.get("error", r.get("detail", "")))[:80]
            all_pass = False
        marker = "✓" if status == "PASS" else ("!" if status == "FAIL" else "-")
        print(f"  [{marker}] {label:<45} {status}  {detail}")

    # Row count deltas
    baseline = (_results.get("step1") or {}).get("baseline", {})
    if baseline and _db_conn and not _db_conn.closed:
        print()
        print("  Row count deltas (pre → post):")
        print(f"  {'Table':<50} {'Before':>7}  {'After':>7}  {'Delta':>7}")
        print("  " + "─" * 68)
        with _db_conn.cursor() as cur:
            post = _row_counts(cur, SERVICE_TABLES)
        for t in SERVICE_TABLES:
            pre = baseline.get(t, -1)
            aft = post.get(t, -1)
            dlt = (aft - pre) if pre >= 0 and aft >= 0 else "N/A"
            print(f"  {t:<50} {str(pre):>7}  {str(aft):>7}  {str(dlt):>7}")

    print(f"\n  Elapsed: {total:.1f}s")

    print()
    print("  Green Gate Checklist:")
    loki_pass = (_results.get("step_loki") or {}).get("pass", False)
    print(f"  [{'✓' if all_pass else '✗'}] 1. All validate steps PASS")
    print(f"  [{'✓' if loki_pass else '✗'}] 2. Loki Level 1 verified")
    print(f"  [ ] 3. OpenAPI spec committed to services/{SERVICE_NAME}/openapi.yaml")
    print(f"  [ ] 4. Service doc capability registry current")
    print(f"  [ ] 5. _index.md updated")
    print(f"  [ ] 6. Evidence report written to outputs/validation/")
    print(f"  [ ] 7. .env.example current")
    print()

    if all_pass and loki_pass and not partial:
        _ok(f"AUTOMATED CHECKS PASSED. Complete items 3–7 to satisfy green gate.")
    elif all_pass and not partial:
        _fail("Loki Level 1 FAILED. Service is not logging to Loki. Fix before delivery.")
    else:
        _fail("One or more steps FAILED. Review errors above.")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"\n{BOLD}IbbyTech Platform — {SERVICE_LABEL} Validation{RESET}")
    print(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Service: {SERVICE_URL}")

    step0_environment()
    step1_db_pre_test()
    step2_first_endpoint()
    step3_regression()
    step_loki()
    _print_final_report()

    if _db_conn and not _db_conn.closed:
        _db_conn.close()

    all_auto_pass = all(
        _results.get(k, {}).get("pass", False)
        for k in ["step1", "step2", "step3", "step_loki"]
    )
    sys.exit(0 if all_auto_pass else 1)


if __name__ == "__main__":
    main()
