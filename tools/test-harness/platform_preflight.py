#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
"""
platform_preflight.py
=====================
IbbyTech Platform — Stage 2 Task Onboarding Check
Part A: Infrastructure Readiness

Run this before starting any build task that touches platform services.
Verifies that all nodes, services, and credentials are in the expected state
before the first line of code is written.

Part B (Capability Pre-check) is a documentation discipline — see the
service doc capability registry sections in .claude/services/. This script
covers Part A only.

Usage
-----
    python tools/test-harness/platform_preflight.py              # check everything
    python tools/test-harness/platform_preflight.py --services   # services only
    python tools/test-harness/platform_preflight.py --infra      # nodes + DB only
    python tools/test-harness/platform_preflight.py --loki       # Loki only

Required: pip install requests
Optional: pip install psycopg2-binary  (enables DB connectivity check)

Environment variables (optional — defaults to platform addresses):
    PGPASSWORD       PostgreSQL password for connectivity check
    PGUSER           PostgreSQL user (default: dba-agent is not used here;
                     use a read-only app user or scraper_app for the check)
"""

import argparse
import os
import socket
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

try:
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)

# Optional — DB check is skipped gracefully if psycopg2 not installed
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
# Platform addresses — matches 01-infrastructure.md
# ─────────────────────────────────────────────────────────────────────────────

SVCNODE_IP   = "192.168.71.220"
DBNODE_IP    = "192.168.71.221"
BRAINNODE_IP = "192.168.71.222"
LOKI_PORT    = 3100

SERVICES = {
    "LLM Gateway":    f"https://llm.platform.ibbytech.com/health",
    "Scraper":        f"http://scrape.platform.ibbytech.com/health",
    "Google Places":  f"http://places.platform.ibbytech.com/health",
    "Reddit Gateway": f"http://reddit.platform.ibbytech.com/health",
    # Telegram Gateway runs in polling mode — no inbound HTTP server.
    # Health is verified via SSH container check (validate_telegram.py).
    # DNS entry required in Pi-hole before HTTP check will work.
}

LOKI_URL = f"http://{SVCNODE_IP}:{LOKI_PORT}"

TIMEOUT = 5

# ─────────────────────────────────────────────────────────────────────────────
# Output helpers
# ─────────────────────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

@dataclass
class CheckResult:
    name: str
    status: str          # PASS | FAIL | WARN | SKIP
    detail: str
    latency_ms: Optional[float] = None
    category: str = ""


def _print_header(title: str) -> None:
    print(f"\n{BOLD}{'─' * 72}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'─' * 72}{RESET}")


def _print_results(results: list[CheckResult]) -> None:
    for r in results:
        if r.status == "PASS":
            marker = f"{GREEN}PASS{RESET}"
        elif r.status == "FAIL":
            marker = f"{RED}FAIL{RESET}"
        elif r.status == "WARN":
            marker = f"{YELLOW}WARN{RESET}"
        else:
            marker = f"{YELLOW}SKIP{RESET}"

        latency = f" ({r.latency_ms:.0f}ms)" if r.latency_ms is not None else ""
        print(f"  {marker}  {r.name:<32} {r.detail}{latency}")


def _summary(all_results: list[CheckResult]) -> bool:
    failed  = [r for r in all_results if r.status == "FAIL"]
    warned  = [r for r in all_results if r.status == "WARN"]
    passed  = [r for r in all_results if r.status == "PASS"]
    skipped = [r for r in all_results if r.status == "SKIP"]

    print(f"\n{'─' * 72}")
    print(f"  Result: {len(passed)} passed  {len(failed)} failed  "
          f"{len(warned)} warned  {len(skipped)} skipped")

    if failed:
        print(f"\n  {RED}{BOLD}PREFLIGHT FAILED — resolve before starting build task:{RESET}")
        for r in failed:
            print(f"    {RED}✗{RESET}  {r.name}: {r.detail}")
    elif warned:
        print(f"\n  {YELLOW}PREFLIGHT PASSED WITH WARNINGS — review before proceeding:{RESET}")
        for r in warned:
            print(f"    {YELLOW}!{RESET}  {r.name}: {r.detail}")
    else:
        print(f"\n  {GREEN}{BOLD}PREFLIGHT PASSED — infrastructure ready.{RESET}")

    print()
    return len(failed) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Check functions
# ─────────────────────────────────────────────────────────────────────────────

def check_tcp(name: str, host: str, port: int) -> CheckResult:
    """TCP connectivity check — confirms a port is open on a node."""
    try:
        start = time.monotonic()
        with socket.create_connection((host, port), timeout=TIMEOUT):
            latency = (time.monotonic() - start) * 1000
        return CheckResult(name, "PASS", f"{host}:{port} reachable", latency)
    except socket.timeout:
        return CheckResult(name, "FAIL", f"{host}:{port} — timeout after {TIMEOUT}s")
    except ConnectionRefusedError:
        return CheckResult(name, "FAIL", f"{host}:{port} — connection refused")
    except OSError as e:
        return CheckResult(name, "FAIL", f"{host}:{port} — {e}")


def check_http_health(name: str, url: str) -> CheckResult:
    """HTTP health endpoint check — confirms a service is running and healthy."""
    try:
        start = time.monotonic()
        resp = requests.get(url, timeout=TIMEOUT, verify=False, allow_redirects=True)
        latency = (time.monotonic() - start) * 1000
        if resp.status_code == 200:
            return CheckResult(name, "PASS", f"HTTP 200", latency)
        elif resp.status_code in (301, 302):
            return CheckResult(name, "WARN", f"HTTP {resp.status_code} (redirect)", latency)
        else:
            return CheckResult(name, "FAIL", f"HTTP {resp.status_code}", latency)
    except requests.exceptions.ConnectionError:
        return CheckResult(name, "FAIL", "Connection refused / DNS error")
    except requests.exceptions.Timeout:
        return CheckResult(name, "FAIL", f"Timeout after {TIMEOUT}s")
    except Exception as e:
        return CheckResult(name, "FAIL", str(e))


def check_loki(loki_url: str) -> CheckResult:
    """Loki readiness check — confirms Loki HTTP API is reachable and responsive."""
    try:
        start = time.monotonic()
        resp = requests.get(f"{loki_url}/ready", timeout=TIMEOUT)
        latency = (time.monotonic() - start) * 1000
        if resp.status_code == 200:
            return CheckResult("Loki HTTP API", "PASS",
                               f"{loki_url} — ready", latency)
        return CheckResult("Loki HTTP API", "FAIL",
                           f"HTTP {resp.status_code}: {resp.text[:100]}", latency)
    except requests.exceptions.ConnectionError:
        return CheckResult("Loki HTTP API", "FAIL",
                           f"{loki_url} — connection refused")
    except Exception as e:
        return CheckResult("Loki HTTP API", "FAIL", str(e))


def check_loki_service_logs(loki_url: str, service_name: str,
                             lookback_minutes: int = 15) -> CheckResult:
    """
    Loki Level 1 check — queries for recent log entries from a named service.
    Used in post-deployment validation (not preflight). Exported here so
    validate_template.py can import it directly.

    Returns PASS if at least one log entry is found in the lookback window.
    Returns FAIL if no entries found or Loki is unreachable.
    Returns WARN if Loki is reachable but query returned unexpected format.
    """
    import json
    now_ns   = int(time.time() * 1e9)
    start_ns = int((time.time() - lookback_minutes * 60) * 1e9)

    query  = f'{{service="{service_name}"}}'
    params = {
        "query": query,
        "start": str(start_ns),
        "end":   str(now_ns),
        "limit": "5",
    }

    try:
        start = time.monotonic()
        resp = requests.get(
            f"{loki_url}/loki/api/v1/query_range",
            params=params,
            timeout=10,
        )
        latency = (time.monotonic() - start) * 1000

        if resp.status_code != 200:
            return CheckResult(
                f"Loki logs ({service_name})", "FAIL",
                f"HTTP {resp.status_code}: {resp.text[:200]}", latency
            )

        data    = resp.json()
        results = data.get("data", {}).get("result", [])

        if not results:
            return CheckResult(
                f"Loki logs ({service_name})", "FAIL",
                f"No log entries for service={service_name!r} in last {lookback_minutes}min. "
                f"Service may not be logging to Loki, or service= label is missing.",
                latency
            )

        total_entries = sum(len(stream.get("values", [])) for stream in results)
        return CheckResult(
            f"Loki logs ({service_name})", "PASS",
            f"{total_entries} log entr{'y' if total_entries == 1 else 'ies'} "
            f"found in last {lookback_minutes}min",
            latency
        )

    except requests.exceptions.ConnectionError:
        return CheckResult(
            f"Loki logs ({service_name})", "FAIL",
            f"Loki unreachable at {loki_url}"
        )
    except Exception as e:
        return CheckResult(
            f"Loki logs ({service_name})", "FAIL", str(e)
        )


def check_db(host: str, port: int) -> CheckResult:
    """PostgreSQL TCP reachability check (does not require credentials)."""
    return check_tcp("dbnode-01 PostgreSQL", host, port)


def check_db_auth() -> CheckResult:
    """
    PostgreSQL authenticated connection check.
    Only runs if PGPASSWORD is set in the environment.
    Uses PGUSER / PGDATABASE / PGHOST if set, otherwise safe defaults.
    """
    if not PSYCOPG2_AVAILABLE:
        return CheckResult("DB authenticated connect", "SKIP",
                           "psycopg2 not installed — pip install psycopg2-binary")

    pw = os.environ.get("PGPASSWORD", "")
    if not pw:
        return CheckResult("DB authenticated connect", "SKIP",
                           "PGPASSWORD not set — skipping auth check")

    config = {
        "host":     os.environ.get("PGHOST",     DBNODE_IP),
        "port":     int(os.environ.get("PGPORT", "5432")),
        "dbname":   os.environ.get("PGDATABASE", "platform_v1"),
        "user":     os.environ.get("PGUSER",     "scraper_app"),
        "password": pw,
        "connect_timeout": TIMEOUT,
    }
    try:
        start = time.monotonic()
        conn = psycopg2.connect(**config)
        latency = (time.monotonic() - start) * 1000
        conn.close()
        return CheckResult(
            "DB authenticated connect", "PASS",
            f"{config['user']}@{config['host']}/{config['dbname']}", latency
        )
    except Exception as e:
        return CheckResult("DB authenticated connect", "FAIL", str(e))


def check_env_credentials(required_vars: list[str]) -> list[CheckResult]:
    """
    Check that required environment variable names are set (non-empty).
    Does NOT log values — presence check only.
    Pass a list of var names required by the task at hand.
    """
    results = []
    for var in required_vars:
        val = os.environ.get(var, "")
        if val:
            results.append(CheckResult(f"Credential: {var}", "PASS", "set"))
        else:
            results.append(CheckResult(f"Credential: {var}", "FAIL",
                                       f"{var} not set in environment"))
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Main preflight runner
# ─────────────────────────────────────────────────────────────────────────────

def run_infra_checks() -> list[CheckResult]:
    """Node reachability and DB connectivity checks."""
    results = []

    _print_header("Part A — Node Reachability")
    node_checks = [
        check_tcp("svcnode-01 HTTP",    SVCNODE_IP,   80),
        check_tcp("svcnode-01 HTTPS",   SVCNODE_IP,   443),
        # Traefik dashboard (:8080) is intentionally internal-only on svcnode-01.
        # Not accessible from laptop — excluded from reachability checks.
        check_db(DBNODE_IP, 5432),
        check_tcp("brainnode-01 SSH",   BRAINNODE_IP, 22),
    ]
    _print_results(node_checks)
    results.extend(node_checks)

    _print_header("Part A — Database Connectivity")
    db_checks = [check_db_auth()]
    _print_results(db_checks)
    results.extend(db_checks)

    return results


def run_service_checks() -> list[CheckResult]:
    """Platform service health endpoint checks."""
    results = []
    _print_header("Part A — Platform Service Health")
    service_checks = [
        check_http_health(name, url) for name, url in SERVICES.items()
    ]
    _print_results(service_checks)
    results.extend(service_checks)
    return results


def run_loki_checks() -> list[CheckResult]:
    """Loki API reachability check."""
    results = []
    _print_header("Part A — Loki Observability Stack")
    loki_checks = [check_loki(LOKI_URL)]
    _print_results(loki_checks)
    results.extend(loki_checks)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IbbyTech Platform — Stage 2 Task Onboarding Preflight Check"
    )
    parser.add_argument("--infra",    action="store_true", help="Node + DB checks only")
    parser.add_argument("--services", action="store_true", help="Platform service health only")
    parser.add_argument("--loki",     action="store_true", help="Loki check only")
    args = parser.parse_args()

    run_all = not any([args.infra, args.services, args.loki])

    print(f"\n{BOLD}IbbyTech Platform — Task Onboarding Preflight{RESET}")
    print(f"Date:    {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Timeout: {TIMEOUT}s per check")
    print(f"Loki:    {LOKI_URL}")

    all_results: list[CheckResult] = []

    if run_all or args.infra:
        all_results.extend(run_infra_checks())

    if run_all or args.services:
        all_results.extend(run_service_checks())

    if run_all or args.loki:
        all_results.extend(run_loki_checks())

    ok = _summary(all_results)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
