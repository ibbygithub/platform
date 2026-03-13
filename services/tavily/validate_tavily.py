#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_tavily.py
==================
IbbyTech Platform — Tavily Gateway Validation

Runs 7-step validation against the platform-tavily container.
Prints a Green Gate checklist summary at exit.

Usage
-----
    python services/tavily/validate_tavily.py

Requires: requests (pip install requests)
"""

import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

TAVILY_HOST    = os.getenv("TAVILY_HOST", "127.0.0.1")
TAVILY_PORT    = int(os.getenv("TAVILY_PORT", "8084"))
CONTAINER_NAME = "platform-tavily"
TIMEOUT        = 10


@dataclass
class CheckResult:
    name:    str
    status:  str          # PASS | FAIL | WARN | SKIP
    detail:  str
    latency: float = 0.0


def _print_header(title: str) -> None:
    print(f"\n{BOLD}{'─' * 72}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'─' * 72}{RESET}")


def _print_result(r: CheckResult) -> None:
    if r.status == "PASS":
        marker = f"{GREEN}PASS{RESET}"
    elif r.status == "FAIL":
        marker = f"{RED}FAIL{RESET}"
    elif r.status == "WARN":
        marker = f"{YELLOW}WARN{RESET}"
    else:
        marker = f"{YELLOW}SKIP{RESET}"
    latency = f"  ({r.latency*1000:.0f}ms)" if r.latency else ""
    print(f"  {marker}  {r.name:<40} {r.detail}{latency}")


def _summary(results: list[CheckResult]) -> None:
    failed = [r for r in results if r.status == "FAIL"]
    warned = [r for r in results if r.status == "WARN"]
    passed = [r for r in results if r.status == "PASS"]
    print(f"\n{'─' * 72}")
    print(f"  Result: {len(passed)} passed  {len(failed)} failed  "
          f"{len(warned)} warnings  (of {len(results)} checks)")
    if failed:
        print(f"\n  {RED}{BOLD}VALIDATION FAILED — resolve before marking task complete:{RESET}")
        for r in failed:
            print(f"    {RED}✗{RESET}  {r.name}: {r.detail}")
        sys.exit(1)
    elif warned:
        print(f"\n  {YELLOW}VALIDATION PASSED WITH WARNINGS:{RESET}")
        for r in warned:
            print(f"    {YELLOW}!{RESET}  {r.name}: {r.detail}")
    else:
        print(f"\n  {GREEN}{BOLD}VALIDATION PASSED — Tavily gateway ready.{RESET}")
    print()


# ── Step 1 — Environment ──────────────────────────────────────────────────────
def check_environment() -> CheckResult:
    """Verify TAVILY_API_KEY is set in the container environment."""
    try:
        result = subprocess.run(
            ["docker", "exec", CONTAINER_NAME, "env"],
            capture_output=True, text=True, timeout=10,
        )
        if "TAVILY_API_KEY=" in result.stdout:
            # Confirm it's not empty or placeholder
            for line in result.stdout.splitlines():
                if line.startswith("TAVILY_API_KEY="):
                    value = line.split("=", 1)[1].strip()
                    if value and value != "tvly-REPLACE_ME":
                        return CheckResult("TAVILY_API_KEY configured", "PASS",
                                           "env var present and non-default")
                    return CheckResult("TAVILY_API_KEY configured", "FAIL",
                                       "TAVILY_API_KEY is empty or still REPLACE_ME placeholder")
        return CheckResult("TAVILY_API_KEY configured", "FAIL",
                           "TAVILY_API_KEY not found in container environment")
    except Exception as exc:
        return CheckResult("TAVILY_API_KEY configured", "FAIL", str(exc))


# ── Step 2 — Container running ────────────────────────────────────────────────
def check_container() -> CheckResult:
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={CONTAINER_NAME}",
             "--filter", "status=running", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=10,
        )
        if CONTAINER_NAME in result.stdout:
            return CheckResult("Container running", "PASS", f"{CONTAINER_NAME} is up")
        return CheckResult("Container running", "FAIL",
                           f"{CONTAINER_NAME} not found in running containers")
    except Exception as exc:
        return CheckResult("Container running", "FAIL", str(exc))


# ── Step 3 — TCP reachability ─────────────────────────────────────────────────
def check_tcp() -> CheckResult:
    t0 = time.monotonic()
    try:
        with socket.create_connection((TAVILY_HOST, TAVILY_PORT), timeout=TIMEOUT):
            latency = time.monotonic() - t0
            return CheckResult("TCP port 8084", "PASS",
                               f"{TAVILY_HOST}:{TAVILY_PORT} reachable", latency)
    except ConnectionRefusedError:
        return CheckResult("TCP port 8084", "FAIL",
                           f"{TAVILY_HOST}:{TAVILY_PORT} — connection refused")
    except socket.timeout:
        return CheckResult("TCP port 8084", "FAIL",
                           f"{TAVILY_HOST}:{TAVILY_PORT} — timeout")
    except Exception as exc:
        return CheckResult("TCP port 8084", "FAIL", str(exc))


# ── Step 4 — Health endpoint ──────────────────────────────────────────────────
def check_health() -> CheckResult:
    import requests as req_lib
    t0 = time.monotonic()
    try:
        r = req_lib.get(f"http://{TAVILY_HOST}:{TAVILY_PORT}/health", timeout=TIMEOUT)
        latency = time.monotonic() - t0
        if r.status_code == 200:
            data = r.json()
            if data.get("ok"):
                return CheckResult("/health endpoint", "PASS",
                                   "returned ok=true", latency)
            err = data.get("error", "ok=false")
            return CheckResult("/health endpoint", "FAIL", err)
        return CheckResult("/health endpoint", "FAIL",
                           f"HTTP {r.status_code}: {r.text[:200]}")
    except Exception as exc:
        return CheckResult("/health endpoint", "FAIL", str(exc))


# ── Step 5 — Live search (English) ───────────────────────────────────────────
def check_search_english() -> CheckResult:
    """Verify a real English query returns results from Tavily."""
    import requests as req_lib
    t0 = time.monotonic()
    try:
        r = req_lib.post(
            f"http://{TAVILY_HOST}:{TAVILY_PORT}/v1/search",
            json={"query": "Tokyo travel tips", "max_results": 2},
            timeout=30,
        )
        latency = time.monotonic() - t0
        if r.status_code == 200:
            data = r.json()
            results = data.get("results", [])
            if results:
                return CheckResult("Search (English query)", "PASS",
                                   f"returned {len(results)} result(s)", latency)
            return CheckResult("Search (English query)", "WARN",
                               "ok=true but 0 results returned", latency)
        return CheckResult("Search (English query)", "FAIL",
                           f"HTTP {r.status_code}: {r.text[:200]}")
    except Exception as exc:
        return CheckResult("Search (English query)", "FAIL", str(exc))


# ── Step 6 — Live search (kanji) ─────────────────────────────────────────────
def check_search_kanji() -> CheckResult:
    """Verify a kanji query works — key capability for Shogun."""
    import requests as req_lib
    t0 = time.monotonic()
    try:
        r = req_lib.post(
            f"http://{TAVILY_HOST}:{TAVILY_PORT}/v1/search",
            json={"query": "東京 おすすめ ラーメン", "max_results": 2},
            timeout=30,
        )
        latency = time.monotonic() - t0
        if r.status_code == 200:
            data = r.json()
            results = data.get("results", [])
            if results:
                return CheckResult("Search (kanji query)", "PASS",
                                   f"returned {len(results)} result(s)", latency)
            return CheckResult("Search (kanji query)", "WARN",
                               "ok=true but 0 results returned", latency)
        return CheckResult("Search (kanji query)", "FAIL",
                           f"HTTP {r.status_code}: {r.text[:200]}")
    except Exception as exc:
        return CheckResult("Search (kanji query)", "FAIL", str(exc))


# ── Step 7 — Domain-restricted search (Tabelog) ───────────────────────────────
def check_search_domain_restricted() -> CheckResult:
    """Verify domain-restricted search works — Tabelog use case for Shogun."""
    import requests as req_lib
    t0 = time.monotonic()
    try:
        r = req_lib.post(
            f"http://{TAVILY_HOST}:{TAVILY_PORT}/v1/search",
            json={
                "query":           "東京 ランチ",
                "max_results":     3,
                "include_domains": ["tabelog.com"],
            },
            timeout=30,
        )
        latency = time.monotonic() - t0
        if r.status_code == 200:
            data    = r.json()
            results = data.get("results", [])
            # Verify returned URLs are actually from tabelog.com
            tabelog_hits = [res for res in results if "tabelog.com" in res.get("url", "")]
            if tabelog_hits:
                return CheckResult("Domain search (tabelog.com)", "PASS",
                                   f"{len(tabelog_hits)} tabelog.com result(s)", latency)
            if results:
                return CheckResult("Domain search (tabelog.com)", "WARN",
                                   f"results returned but none from tabelog.com ({len(results)} total)",
                                   latency)
            return CheckResult("Domain search (tabelog.com)", "WARN",
                               "ok=true but 0 results — may be normal for domain restriction", latency)
        return CheckResult("Domain search (tabelog.com)", "FAIL",
                           f"HTTP {r.status_code}: {r.text[:200]}")
    except Exception as exc:
        return CheckResult("Domain search (tabelog.com)", "FAIL", str(exc))


# ── Green Gate report ─────────────────────────────────────────────────────────
def print_green_gate(results: list[CheckResult]) -> None:
    _print_header("Green Gate — Tavily Gateway Checklist")
    checks = [
        ("TAVILY_API_KEY configured",  "API key present in container env"),
        ("Container running",          "platform-tavily up and healthy"),
        ("TCP port 8084",              "reachable from host"),
        ("/health endpoint",           "gateway self-reports healthy"),
        ("Search (English query)",     "English search functional"),
        ("Search (kanji query)",       "Kanji search functional — Shogun core requirement"),
        ("Domain search (tabelog.com)", "Domain-restricted search functional — Shogun Tabelog use case"),
    ]
    for name, description in checks:
        match = next((r for r in results if r.name == name), None)
        if match:
            _print_result(match)
        else:
            print(f"  {'SKIP':>4}  {name:<40} {description}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    _print_header("Tavily Gateway — Validation")

    results: list[CheckResult] = []

    # Step 1 — Environment (requires docker exec — must run on svcnode-01)
    r = check_environment()
    _print_result(r)
    results.append(r)
    if r.status == "FAIL":
        # API key check failed — skip remaining steps that would also fail
        _summary(results)
        return

    # Step 2 — Container
    r = check_container()
    _print_result(r)
    results.append(r)
    if r.status == "FAIL":
        _summary(results)
        return

    # Step 3 — TCP
    r = check_tcp()
    _print_result(r)
    results.append(r)
    if r.status == "FAIL":
        _summary(results)
        return

    # Steps 4–7 — HTTP checks (require requests library)
    try:
        import requests  # noqa: F401
    except ImportError:
        print(f"  {YELLOW}WARN{RESET}  requests library not installed — skipping HTTP checks")
        print(f"       Run: pip install requests")
        results += [
            CheckResult("/health endpoint",           "SKIP", "requests not installed"),
            CheckResult("Search (English query)",     "SKIP", "requests not installed"),
            CheckResult("Search (kanji query)",       "SKIP", "requests not installed"),
            CheckResult("Domain search (tabelog.com)", "SKIP", "requests not installed"),
        ]
        print_green_gate(results)
        _summary(results)
        return

    r = check_health()
    _print_result(r)
    results.append(r)
    if r.status == "FAIL":
        _summary(results)
        return

    r = check_search_english()
    _print_result(r)
    results.append(r)

    r = check_search_kanji()
    _print_result(r)
    results.append(r)

    r = check_search_domain_restricted()
    _print_result(r)
    results.append(r)

    print_green_gate(results)
    _summary(results)


if __name__ == "__main__":
    main()
