#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
"""
check_logstack.py
=================
IbbyTech Platform — Logstack Health Check

Checks the health of the core observability stack on svcnode-01:
  - Loki (log ingestion)
  - Grafana (dashboards)
  - Grafana Alloy (log collector/shipper)

Run this after any svcnode-01 reboot before starting work that depends
on observability (Loki log verification, Grafana dashboards).

Loki has a startup readiness window — the ingester takes 15-30 seconds
after container start before it is ready. This script polls with retries
so you get a definitive PASS or FAIL rather than a false 503.

Usage
-----
    python tools/ops/check_logstack.py              # check all
    python tools/ops/check_logstack.py --wait 60   # wait up to 60s for Loki
    python tools/ops/check_logstack.py --loki-only

Required: pip install requests
SSH access to svcnode-01 via devops-agent required for container checks.
"""

import argparse
import subprocess
import time
from dataclasses import dataclass
from typing import Optional

try:
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

SVCNODE_IP   = "192.168.71.220"
LOKI_URL     = f"http://{SVCNODE_IP}:3100"
GRAFANA_URL  = f"http://{SVCNODE_IP}:3000"

SSH_KEY      = "~/.ssh/devops-agent_ed25519_clean"
SSH_TARGET   = f"devops-agent@{SVCNODE_IP}"

LOKI_CONTAINERS    = ["logstack-loki-1"]
GRAFANA_CONTAINERS = ["logstack-grafana-1"]
ALLOY_CONTAINERS   = ["logstack-alloy-1"]

HTTP_TIMEOUT = 5

# ─────────────────────────────────────────────────────────────────────────────
# Output
# ─────────────────────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


@dataclass
class Result:
    name: str
    status: str    # PASS | FAIL | WARN | SKIP
    detail: str
    latency_ms: Optional[float] = None


def _hdr(title: str) -> None:
    print(f"\n{BOLD}  {title}{RESET}")
    print(f"  {'─' * 60}")


def _print(r: Result) -> None:
    if r.status == "PASS":
        c = GREEN
    elif r.status == "FAIL":
        c = RED
    elif r.status == "WARN":
        c = YELLOW
    else:
        c = YELLOW
    lat = f" ({r.latency_ms:.0f}ms)" if r.latency_ms is not None else ""
    print(f"  {c}{r.status:<4}{RESET}  {r.name:<35} {r.detail}{lat}")


# ─────────────────────────────────────────────────────────────────────────────
# SSH helper
# ─────────────────────────────────────────────────────────────────────────────

import os
_SSH_KEY_EXPANDED = os.path.expanduser(SSH_KEY)

def _ssh(command: str, timeout: int = 15) -> tuple[bool, str]:
    cmd = [
        "ssh", "-i", _SSH_KEY_EXPANDED,
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        SSH_TARGET, command,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return False, f"SSH timed out after {timeout}s"
    except Exception as e:
        return False, str(e)


# ─────────────────────────────────────────────────────────────────────────────
# Checks
# ─────────────────────────────────────────────────────────────────────────────

def check_loki_ready(wait_seconds: int = 0) -> Result:
    """
    Poll Loki /ready endpoint. Retries for wait_seconds if not ready.
    After a reboot, Loki ingester needs ~15-30s before it reports ready.
    """
    deadline = time.time() + wait_seconds
    attempt  = 0

    while True:
        attempt += 1
        try:
            start = time.monotonic()
            resp  = requests.get(f"{LOKI_URL}/ready", timeout=HTTP_TIMEOUT)
            lat   = (time.monotonic() - start) * 1000

            if resp.status_code == 200 and resp.text.strip() == "ready":
                waited = f" (attempt {attempt})" if attempt > 1 else ""
                return Result("Loki /ready", "PASS",
                              f"ingester ready{waited}", lat)

            detail = f"HTTP {resp.status_code}: {resp.text.strip()[:80]}"

            if time.time() < deadline:
                remaining = int(deadline - time.time())
                print(f"  [WAIT] Loki not ready yet ({detail}) — "
                      f"retrying ({remaining}s remaining) ...")
                time.sleep(3)
                continue

            return Result("Loki /ready", "FAIL", detail, lat)

        except requests.exceptions.ConnectionError:
            detail = f"{LOKI_URL} — connection refused"
            if time.time() < deadline:
                remaining = int(deadline - time.time())
                print(f"  [WAIT] {detail} — retrying ({remaining}s remaining) ...")
                time.sleep(3)
                continue
            return Result("Loki /ready", "FAIL", detail)

        except Exception as e:
            return Result("Loki /ready", "FAIL", str(e))


def check_loki_push() -> Result:
    """
    Send a test log entry to Loki and verify it was accepted.
    This confirms the ingester is not just ready but actually accepting writes.
    """
    payload = {
        "streams": [{
            "stream": {"service": "logstack-check", "level": "info"},
            "values": [[
                str(int(time.time() * 1e9)),
                "logstack health check — write test"
            ]]
        }]
    }
    try:
        start = time.monotonic()
        resp  = requests.post(
            f"{LOKI_URL}/loki/api/v1/push",
            json=payload,
            timeout=HTTP_TIMEOUT,
        )
        lat = (time.monotonic() - start) * 1000
        if resp.status_code == 204:
            return Result("Loki push (write test)", "PASS",
                          "log entry accepted (HTTP 204)", lat)
        return Result("Loki push (write test)", "FAIL",
                      f"HTTP {resp.status_code}: {resp.text[:80]}", lat)
    except Exception as e:
        return Result("Loki push (write test)", "FAIL", str(e))


def check_loki_query() -> Result:
    """
    Query Loki for the test entry just pushed by check_loki_push().
    Confirms the ingester is serving reads as well as accepting writes.
    """
    now_ns   = int(time.time() * 1e9)
    start_ns = int((time.time() - 120) * 1e9)   # last 2 minutes
    params   = {
        "query": '{service="logstack-check"}',
        "start": str(start_ns),
        "end":   str(now_ns),
        "limit": "5",
    }
    try:
        start = time.monotonic()
        resp  = requests.get(
            f"{LOKI_URL}/loki/api/v1/query_range",
            params=params,
            timeout=HTTP_TIMEOUT,
        )
        lat = (time.monotonic() - start) * 1000
        if resp.status_code != 200:
            return Result("Loki query (read test)", "FAIL",
                          f"HTTP {resp.status_code}: {resp.text[:80]}", lat)
        results = resp.json().get("data", {}).get("result", [])
        if results:
            count = sum(len(s.get("values", [])) for s in results)
            return Result("Loki query (read test)", "PASS",
                          f"{count} entr{'y' if count == 1 else 'ies'} found", lat)
        return Result("Loki query (read test)", "WARN",
                      "No entries found — ingester may still be indexing (normal within 5s)", lat)
    except Exception as e:
        return Result("Loki query (read test)", "FAIL", str(e))


def check_grafana() -> Result:
    """Check Grafana health API."""
    try:
        start = time.monotonic()
        resp  = requests.get(f"{GRAFANA_URL}/api/health", timeout=HTTP_TIMEOUT)
        lat   = (time.monotonic() - start) * 1000
        if resp.status_code == 200:
            data = resp.json()
            db   = data.get("database", "unknown")
            return Result("Grafana /api/health", "PASS",
                          f"database={db}", lat)
        return Result("Grafana /api/health", "FAIL",
                      f"HTTP {resp.status_code}", lat)
    except requests.exceptions.ConnectionError:
        return Result("Grafana /api/health", "FAIL",
                      f"{GRAFANA_URL} — connection refused")
    except Exception as e:
        return Result("Grafana /api/health", "FAIL", str(e))


def check_containers_running() -> list[Result]:
    """SSH to svcnode-01 and confirm all logstack containers are running."""
    results = []
    all_containers = LOKI_CONTAINERS + GRAFANA_CONTAINERS + ALLOY_CONTAINERS

    ok, output = _ssh(
        "docker ps --format '{{.Names}}\\t{{.Status}}' | grep logstack"
    )

    if not ok:
        for name in all_containers:
            results.append(Result(f"Container: {name}", "FAIL",
                                  f"SSH error: {output[:80]}"))
        return results

    running = {}
    for line in output.splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2:
            running[parts[0].strip()] = parts[1].strip()

    for name in all_containers:
        if name in running:
            status = running[name]
            ok_status = status.lower().startswith("up")
            results.append(Result(
                f"Container: {name}",
                "PASS" if ok_status else "FAIL",
                status
            ))
        else:
            results.append(Result(
                f"Container: {name}", "FAIL",
                "Not found in docker ps output — container not running"
            ))

    return results


def check_alloy_shipping() -> Result:
    """
    Check Grafana Alloy health via its UI port (12345).
    Alloy is the log shipper — if it's not healthy, logs won't reach Loki.
    """
    try:
        start = time.monotonic()
        resp  = requests.get(f"http://{SVCNODE_IP}:12345/ready", timeout=HTTP_TIMEOUT)
        lat   = (time.monotonic() - start) * 1000
        if resp.status_code == 200:
            return Result("Alloy /ready", "PASS", "log shipper ready", lat)
        return Result("Alloy /ready", "WARN",
                      f"HTTP {resp.status_code} — Alloy may still be initialising", lat)
    except requests.exceptions.ConnectionError:
        return Result("Alloy /ready", "WARN",
                      "Port 12345 not reachable from laptop — check from svcnode-01 if needed")
    except Exception as e:
        return Result("Alloy /ready", "FAIL", str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="IbbyTech Platform — Logstack (Loki + Grafana + Alloy) Health Check"
    )
    parser.add_argument("--wait",      type=int, default=45,
                        help="Seconds to wait for Loki readiness (default: 45). "
                             "Use 0 for single-shot check.")
    parser.add_argument("--loki-only", action="store_true",
                        help="Check Loki only (skip Grafana and Alloy)")
    args = parser.parse_args()

    print(f"\n{BOLD}IbbyTech Platform — Logstack Health Check{RESET}")
    print(f"Date:    {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Loki:    {LOKI_URL}")
    print(f"Grafana: {GRAFANA_URL}")
    if args.wait > 0:
        print(f"Waiting: up to {args.wait}s for Loki readiness (post-reboot mode)")

    all_results: list[Result] = []

    # ── Container status (SSH) ────────────────────────────────────────────────
    _hdr("Container Status (via SSH)")
    container_results = check_containers_running()
    for r in container_results:
        _print(r)
    all_results.extend(container_results)

    # ── Loki ─────────────────────────────────────────────────────────────────
    _hdr("Loki — Log Ingestion")
    loki_ready = check_loki_ready(wait_seconds=args.wait)
    _print(loki_ready)
    all_results.append(loki_ready)

    if loki_ready.status == "PASS":
        loki_push  = check_loki_push()
        _print(loki_push)
        all_results.append(loki_push)

        loki_query = check_loki_query()
        _print(loki_query)
        all_results.append(loki_query)
    else:
        print(f"  {YELLOW}SKIP{RESET}  Loki write/read tests skipped — ingester not ready")

    if not args.loki_only:
        # ── Grafana ───────────────────────────────────────────────────────────
        _hdr("Grafana — Dashboards")
        grafana = check_grafana()
        _print(grafana)
        all_results.append(grafana)

        # ── Alloy ─────────────────────────────────────────────────────────────
        _hdr("Grafana Alloy — Log Shipper")
        alloy = check_alloy_shipping()
        _print(alloy)
        all_results.append(alloy)

    # ── Summary ───────────────────────────────────────────────────────────────
    failed = [r for r in all_results if r.status == "FAIL"]
    warned = [r for r in all_results if r.status == "WARN"]
    passed = [r for r in all_results if r.status == "PASS"]

    print(f"\n  {'─' * 60}")
    print(f"  Result: {len(passed)} passed  {len(failed)} failed  {len(warned)} warned")

    if failed:
        print(f"\n  {RED}{BOLD}LOGSTACK DEGRADED — investigate before relying on observability:{RESET}")
        for r in failed:
            print(f"    {RED}x{RESET}  {r.name}: {r.detail}")
        print(f"\n  Recovery steps:")
        print(f"    ssh -i ~/.ssh/devops-agent_ed25519_clean devops-agent@{SVCNODE_IP}")
        print(f"    cd /opt/logstack && docker compose restart")
        print(f"    # Then re-run this script with --wait 60")
    elif warned:
        print(f"\n  {YELLOW}LOGSTACK OPERATIONAL WITH WARNINGS — review above{RESET}")
    else:
        print(f"\n  {GREEN}{BOLD}LOGSTACK HEALTHY — all checks passed.{RESET}")

    print()
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
