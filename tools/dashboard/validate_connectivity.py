#!/usr/bin/env python3
"""
validate_connectivity.py
Phase 0: Network and port reachability check for all platform services.

Run from: C:/git/work/platform/tools/dashboard/
Required env vars: none -- all checks are unauthenticated reachability only
"""

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

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

TIMEOUT = 5  # seconds per check


@dataclass
class CheckResult:
    name: str
    target: str
    method: str
    passed: bool
    detail: str
    latency_ms: Optional[float] = None
    skipped: bool = False


def http_check(name: str, url: str) -> CheckResult:
    try:
        start = time.monotonic()
        resp = requests.get(url, timeout=TIMEOUT, verify=False, allow_redirects=True)
        latency = (time.monotonic() - start) * 1000
        return CheckResult(name, url, "HTTP GET", True, f"HTTP {resp.status_code}", latency)
    except requests.exceptions.ConnectionError:
        return CheckResult(name, url, "HTTP GET", False, "Connection refused / DNS error")
    except requests.exceptions.Timeout:
        return CheckResult(name, url, "HTTP GET", False, f"Timeout after {TIMEOUT}s")
    except Exception as e:
        return CheckResult(name, url, "HTTP GET", False, str(e))


def tcp_check(name: str, host: str, port: int) -> CheckResult:
    target = f"{host}:{port}"
    try:
        start = time.monotonic()
        with socket.create_connection((host, port), timeout=TIMEOUT):
            latency = (time.monotonic() - start) * 1000
        return CheckResult(name, target, "TCP connect", True, "Port open", latency)
    except socket.timeout:
        return CheckResult(name, target, "TCP connect", False, f"Timeout after {TIMEOUT}s")
    except ConnectionRefusedError:
        return CheckResult(name, target, "TCP connect", False, "Connection refused")
    except OSError as e:
        return CheckResult(name, target, "TCP connect", False, str(e))


def skip_check(name: str, reason: str) -> CheckResult:
    return CheckResult(name, "(none)", "--", False, reason, skipped=True)


def print_results(results: list[CheckResult]) -> bool:
    col_name   = 30
    col_target = 38
    col_method = 13

    print(f"\n{BOLD}{'-' * 100}{RESET}")
    print(f"{BOLD}{'CHECK':<{col_name}} {'TARGET':<{col_target}} {'METHOD':<{col_method}} {'STATUS':<8}  DETAIL{RESET}")
    print(f"{'-' * 100}")

    for r in results:
        if r.skipped:
            status_str = f"{YELLOW}SKIP{RESET}"
        elif r.passed:
            status_str = f"{GREEN}PASS{RESET}"
        else:
            status_str = f"{RED}FAIL{RESET}"

        latency_str = f" ({r.latency_ms:.0f}ms)" if r.latency_ms is not None else ""
        target_str  = r.target[:col_target - 1] if len(r.target) >= col_target else r.target
        detail_str  = r.detail + latency_str

        # pad status_str accounts for invisible ANSI escape bytes
        print(f"{r.name:<{col_name}} {target_str:<{col_target}} {r.method:<{col_method}} {status_str:<8}  {detail_str}")

    print(f"{'-' * 100}")

    failed  = [r for r in results if not r.passed and not r.skipped]
    skipped = [r for r in results if r.skipped]

    if failed:
        print(f"\n{RED}{BOLD}{len(failed)} check(s) FAILED.{RESET} Investigate before proceeding to Phase 1.")
        for r in failed:
            print(f"  {RED}*{RESET} {r.name}: {r.detail}")
    else:
        print(f"\n{GREEN}{BOLD}All reachability checks passed.{RESET}")

    if skipped:
        print(f"\n{YELLOW}Skipped ({len(skipped)}):{RESET}")
        for r in skipped:
            print(f"  * {r.name}: {r.detail}")

    print()
    return len(failed) == 0


def main():
    print(f"\n{BOLD}IbbyTech Platform -- Connectivity Validation{RESET}")
    print(f"Date:    {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Timeout: {TIMEOUT}s per check")

    results: list[CheckResult] = []

    # HTTP checks -- Traefik-routed services
    results.append(http_check("svcnode-01 (direct IP)",   "http://192.168.71.220"))
    results.append(http_check("LLM Gateway",              "https://llm.platform.ibbytech.com"))
    # Scraper, Places, Telegram: no TLS cert in Traefik -- use HTTP (internal network only)
    results.append(http_check("Scraper",                  "http://scrape.platform.ibbytech.com"))
    results.append(http_check("Google Places",            "http://places.platform.ibbytech.com"))
    results.append(http_check("Telegram Gateway",         "http://telegram.platform.ibbytech.com"))

    # Reddit: no FQDN in _index.md -- service doc pending
    results.append(skip_check(
        "Reddit Gateway",
        "No FQDN documented in _index.md -- service doc pending, run /register-service"
    ))

    # TCP check -- dbnode-01 PostgreSQL
    results.append(tcp_check("dbnode-01 PostgreSQL", "192.168.71.221", 5432))

    all_passed = print_results(results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
