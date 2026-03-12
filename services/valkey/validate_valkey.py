#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_valkey.py
==================
IbbyTech Platform — Valkey Service Validation

Runs 7-step validation against the platform-valkey container.
Prints a Green Gate checklist summary at exit.

Usage
-----
    python services/valkey/validate_valkey.py

Required: pip install redis
"""

import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass

# ── Colour helpers ─────────────────────────────────────────────────────────────
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

VALKEY_HOST = os.getenv("VALKEY_HOST", "127.0.0.1")
VALKEY_PORT = int(os.getenv("VALKEY_PORT", "6379"))
VALKEY_PASSWORD = os.getenv("VALKEY_PASSWORD", "")
CONTAINER_NAME = "platform-valkey"
TIMEOUT = 5


@dataclass
class CheckResult:
    name: str
    status: str          # PASS | FAIL | WARN | SKIP
    detail: str
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
    print(f"  {marker}  {r.name:<36} {r.detail}{latency}")


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
        print(f"\n  {GREEN}{BOLD}VALIDATION PASSED — Valkey service ready.{RESET}")
    print()


# ── Step 1 — Environment ───────────────────────────────────────────────────────
def check_environment() -> CheckResult:
    if not VALKEY_PASSWORD:
        return CheckResult("VALKEY_PASSWORD set", "FAIL",
                           "VALKEY_PASSWORD is not set — required for auth")
    return CheckResult("VALKEY_PASSWORD set", "PASS", "env var present")


# ── Step 2 — Container running ─────────────────────────────────────────────────
def check_container() -> CheckResult:
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={CONTAINER_NAME}",
             "--filter", "status=running", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=10
        )
        if CONTAINER_NAME in result.stdout:
            return CheckResult("Container running", "PASS",
                               f"{CONTAINER_NAME} is up")
        return CheckResult("Container running", "FAIL",
                           f"{CONTAINER_NAME} not found in running containers")
    except Exception as e:
        return CheckResult("Container running", "FAIL", str(e))


# ── Step 3 — TCP reachability ──────────────────────────────────────────────────
def check_tcp() -> CheckResult:
    t0 = time.monotonic()
    try:
        with socket.create_connection((VALKEY_HOST, VALKEY_PORT), timeout=TIMEOUT):
            latency = time.monotonic() - t0
            return CheckResult("TCP port 6379", "PASS",
                               f"{VALKEY_HOST}:{VALKEY_PORT} reachable", latency)
    except ConnectionRefusedError:
        return CheckResult("TCP port 6379", "FAIL",
                           f"{VALKEY_HOST}:{VALKEY_PORT} — connection refused")
    except socket.timeout:
        return CheckResult("TCP port 6379", "FAIL",
                           f"{VALKEY_HOST}:{VALKEY_PORT} — timeout")
    except Exception as e:
        return CheckResult("TCP port 6379", "FAIL", str(e))


# ── Step 4 — PING ─────────────────────────────────────────────────────────────
def check_ping(client) -> CheckResult:
    t0 = time.monotonic()
    try:
        resp = client.ping()
        latency = time.monotonic() - t0
        if resp:
            return CheckResult("PING", "PASS", "PONG received", latency)
        return CheckResult("PING", "FAIL", f"Unexpected response: {resp}")
    except Exception as e:
        return CheckResult("PING", "FAIL", str(e))


# ── Step 5 — SET / GET functional ─────────────────────────────────────────────
def check_set_get(client) -> CheckResult:
    t0 = time.monotonic()
    test_key = "platform:validate:probe"
    test_val = "ok"
    try:
        client.set(test_key, test_val, ex=30)
        result = client.get(test_key)
        latency = time.monotonic() - t0
        if result == test_val:
            client.delete(test_key)
            return CheckResult("SET / GET round-trip", "PASS",
                               "write and read verified", latency)
        return CheckResult("SET / GET round-trip", "FAIL",
                           f"Expected '{test_val}', got '{result}'")
    except Exception as e:
        return CheckResult("SET / GET round-trip", "FAIL", str(e))


# ── Step 6 — Loki ─────────────────────────────────────────────────────────────
def check_loki() -> CheckResult:
    # Valkey emits logs to Docker stdout only — no Loki label.
    # Validate via docker logs instead.
    try:
        result = subprocess.run(
            ["docker", "logs", "--tail", "5", CONTAINER_NAME],
            capture_output=True, text=True, timeout=10
        )
        output = (result.stdout + result.stderr).strip()
        if output:
            return CheckResult("Docker logs", "PASS",
                               "container producing output (no Loki — stdout only)")
        return CheckResult("Docker logs", "WARN",
                           "no recent log output (container may be idle)")
    except Exception as e:
        return CheckResult("Docker logs", "SKIP", f"docker logs unavailable: {e}")


# ── Step 7 — Green Gate report ────────────────────────────────────────────────
def print_green_gate(results: list[CheckResult]) -> None:
    _print_header("Green Gate — Valkey Service Checklist")
    checks = [
        ("Container running",   "platform-valkey up and healthy"),
        ("TCP port 6379",       "reachable from host"),
        ("PING",                "auth + PING functional"),
        ("SET / GET round-trip","write and read verified"),
        ("Docker logs",         "container producing output"),
    ]
    for name, description in checks:
        match = next((r for r in results if r.name == name), None)
        if match:
            _print_result(match)
        else:
            print(f"  {'SKIP':>4}  {name:<36} {description}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    _print_header("Valkey Service — Validation")

    results: list[CheckResult] = []

    # Step 1 — Environment
    r = check_environment()
    _print_result(r)
    results.append(r)
    if r.status == "FAIL":
        _summary(results)
        return

    # Step 2 — Container
    r = check_container()
    _print_result(r)
    results.append(r)

    # Step 3 — TCP
    r = check_tcp()
    _print_result(r)
    results.append(r)
    if r.status == "FAIL":
        # Can't proceed to redis checks without TCP
        results.append(CheckResult("PING", "SKIP", "TCP failed — skipping"))
        results.append(CheckResult("SET / GET round-trip", "SKIP", "TCP failed — skipping"))
        results.append(check_loki())
        print_green_gate(results)
        _summary(results)
        return

    # Steps 4–5 — Redis protocol checks
    try:
        import redis as redis_lib
        client = redis_lib.Redis(
            host=VALKEY_HOST,
            port=VALKEY_PORT,
            password=VALKEY_PASSWORD,
            decode_responses=True,
            socket_timeout=TIMEOUT,
        )
        results.append(check_ping(client))
        results.append(check_set_get(client))
    except ImportError:
        results.append(CheckResult("PING", "FAIL",
                                   "redis package not installed — run: pip install redis"))
        results.append(CheckResult("SET / GET round-trip", "SKIP",
                                   "redis package missing"))

    # Step 6 — Logs
    results.append(check_loki())

    for r in results[3:]:   # already printed steps 1–3
        _print_result(r)

    # Step 7 — Green Gate
    print_green_gate(results)
    _summary(results)


if __name__ == "__main__":
    main()
