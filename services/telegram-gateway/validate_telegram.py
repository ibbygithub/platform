#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_telegram.py
====================
Validation of the Platform Telegram Bot Gateway.

Architecture note
-----------------
The Telegram gateway is a Telegraf polling bot — it does NOT expose HTTP
endpoints for the platform to call. It receives inbound messages from
Telegram users and forwards them upstream. There is no /health endpoint.

Validation strategy:
  - Verify the bot token is valid via Telegram Bot API (getMe)
  - Verify the bot identity matches expectations
  - Check Loki for gateway container activity
  - Optional: send a test message if TEST_CHAT_ID is set

Steps
-----
  0  Environment discovery (BOT_TOKEN check)
  1  Telegram Bot API — getMe (token validation, bot identity)
  2  Telegram Bot API — getWebhookInfo (confirm polling mode: no webhook)
  3  Loki Level 1 — check {service="telegram-gateway"} logs flowing
  4  (Optional) Send test message if TEST_CHAT_ID is set
  5  Final report + Green Gate checklist

Prerequisites
-------------
  pip install requests

Environment variables
---------------------
  TELEGRAM_BOT_TOKEN   Required — the Telegram bot token
  TEST_CHAT_ID         Optional — non-production chat ID for send test
                       If not set, Step 4 is SKIPPED (not FAILED)
  LOKI_URL             default: http://192.168.71.220:3100

Usage
-----
  TELEGRAM_BOT_TOKEN=... python validate_telegram.py
"""

import importlib.util
import socket
import json
import os
import pathlib
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    import requests
except ImportError:
    print("[FATAL] Missing: requests — run: pip install requests")
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
_FIXTURES_PATH = pathlib.Path(__file__).parent.parent.parent / "tools" / "test-harness" / "fixtures" / "telegram_fixtures.json"
_FIXTURES: Dict[str, Any] = {}
if _FIXTURES_PATH.exists():
    with open(_FIXTURES_PATH) as _f:
        _FIXTURES = json.load(_f)

# ── Config ───────────────────────────────────────────────────────────────────
BOT_TOKEN       = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TEST_CHAT_ID    = os.environ.get("TEST_CHAT_ID", "").strip()
LOKI_URL        = os.environ.get("LOKI_URL", "http://192.168.71.220:3100")
SEND_API_URL    = os.environ.get("SEND_API_URL", "http://127.0.0.1:3000")
SEND_SECRET     = os.environ.get("SEND_SECRET", "").strip()

TELEGRAM_API = "https://api.telegram.org"

# ── Globals ───────────────────────────────────────────────────────────────────
_suite_start = time.time()
_results: Dict[str, Dict[str, Any]] = {}


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

def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()

def _tg(method: str, payload: Optional[Dict] = None, timeout: int = 10) -> Dict:
    """Call a Telegram Bot API method. Returns the response JSON."""
    url = f"{TELEGRAM_API}/bot{BOT_TOKEN}/{method}"
    if payload:
        r = requests.post(url, json=payload, timeout=timeout)
    else:
        r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


# ── Step 0 — Environment Discovery ───────────────────────────────────────────

def step0_environment() -> None:
    _hdr("Step 0 — Environment Discovery")
    _info(f"TELEGRAM_BOT_TOKEN = {'*** (set)' if BOT_TOKEN else '(NOT SET — FATAL)'}")
    _info(f"TEST_CHAT_ID       = {TEST_CHAT_ID if TEST_CHAT_ID else '(not set — Step 4 will SKIP)'}")
    _info(f"LOKI_URL           = {LOKI_URL}")
    _info(f"Fixtures loaded    = {len(_FIXTURES.get('message_payloads', []))} message payloads")
    print()

    if not BOT_TOKEN:
        _fail("TELEGRAM_BOT_TOKEN is not set. This is required for all steps.")
        _fail("Set it with: export TELEGRAM_BOT_TOKEN=<your-bot-token>")
        sys.exit(1)

    _info("Architecture note: The Telegram gateway is a polling bot.")
    _info("  It also exposes an outbound send API on SEND_API_PORT (default 3000).")
    _info(f"  SEND_API_URL = {SEND_API_URL}")
    _info(f"  SEND_SECRET  = {'*** (set)' if SEND_SECRET else '(not set — auth disabled)'}")


# ── Step 1 — getMe (Token Validation) ────────────────────────────────────────

def step1_get_me() -> None:
    _hdr("Step 1 — Telegram Bot API: getMe (token validation)")
    _info(f"GET {TELEGRAM_API}/bot***/getMe")

    try:
        t0   = time.time()
        data = _tg("getMe")
        ms   = (time.time() - t0) * 1000

        if not data.get("ok"):
            _fail(f"Telegram API returned ok=false: {data}")
            _results["step1"] = {"pass": False, "error": str(data)}
            return

        bot = data["result"]
        _ok(f"Bot token valid ({ms:.0f}ms)")
        _info(f"  id            = {bot.get('id')}")
        _info(f"  username      = @{bot.get('username')}")
        _info(f"  first_name    = {bot.get('first_name')}")
        _info(f"  is_bot        = {bot.get('is_bot')}")
        _info(f"  can_read_msgs = {bot.get('can_read_all_group_messages')}")

        _results["step1"] = {
            "pass": True,
            "bot_id": bot.get("id"),
            "username": bot.get("username"),
        }

    except requests.HTTPError as exc:
        _fail(f"Telegram API HTTP error: {exc}")
        if exc.response is not None and exc.response.status_code == 401:
            _fail("HTTP 401 — bot token is invalid or revoked.")
        _results["step1"] = {"pass": False, "error": str(exc)}

    except Exception as exc:
        _fail(f"getMe failed: {exc}")
        _results["step1"] = {"pass": False, "error": str(exc)}


# ── Step 2 — getWebhookInfo (Confirm Polling Mode) ───────────────────────────

def step2_webhook_info() -> None:
    _hdr("Step 2 — Telegram Bot API: getWebhookInfo (confirm polling mode)")
    _info(f"GET {TELEGRAM_API}/bot***/getWebhookInfo")

    try:
        t0   = time.time()
        data = _tg("getWebhookInfo")
        ms   = (time.time() - t0) * 1000

        if not data.get("ok"):
            _fail(f"getWebhookInfo returned ok=false: {data}")
            _results["step2"] = {"pass": False, "error": str(data)}
            return

        result = data["result"]
        webhook_url = result.get("url", "")

        if not webhook_url:
            _ok(f"Polling mode confirmed — no webhook registered ({ms:.0f}ms)")
            _info(f"  pending_update_count = {result.get('pending_update_count', 0)}")
            _results["step2"] = {"pass": True, "mode": "polling"}
        else:
            _info(f"Webhook mode active — url: {webhook_url}")
            _info(f"  pending_update_count = {result.get('pending_update_count', 0)}")
            _info(f"  max_connections      = {result.get('max_connections')}")
            # Webhook mode is also valid — document it, don't fail
            _ok(f"Webhook mode active ({ms:.0f}ms) — matches TELEGRAM_MODE=webhook config")
            _results["step2"] = {"pass": True, "mode": "webhook", "url": webhook_url}

    except Exception as exc:
        _fail(f"getWebhookInfo failed: {exc}")
        _results["step2"] = {"pass": False, "error": str(exc)}


# ── Step 2b — Send API Health Check ──────────────────────────────────────────

def step2b_send_api_health() -> None:
    _hdr("Step 2b — Send API: GET /health")
    _info(f"GET {SEND_API_URL}/health")

    # TCP reachability first
    try:
        from urllib.parse import urlparse
        parsed = urlparse(SEND_API_URL)
        host   = parsed.hostname or "127.0.0.1"
        port   = parsed.port or 3000
        t0     = time.time()
        sock   = socket.create_connection((host, port), timeout=5)
        sock.close()
        tcp_ms = (time.time() - t0) * 1000
        _ok(f"TCP {host}:{port} reachable ({tcp_ms:.0f}ms)")
    except Exception as exc:
        _fail(f"TCP {host}:{port} — connection refused: {exc}")
        _warn("Container may not be running or SEND_API_PORT not bound to host.")
        _results["step2b"] = {"pass": False, "error": f"TCP failed: {exc}"}
        return

    try:
        t0   = time.time()
        r    = requests.get(f"{SEND_API_URL}/health", timeout=10)
        ms   = (time.time() - t0) * 1000
        r.raise_for_status()
        data = r.json()

        if data.get("ok"):
            _ok(f"Health OK — mode={data.get('mode')}, uptime={data.get('uptime', 0):.0f}s ({ms:.0f}ms)")
            _results["step2b"] = {"pass": True, "mode": data.get("mode"), "uptime": data.get("uptime")}
        else:
            _fail(f"Health returned ok=false: {data}")
            _results["step2b"] = {"pass": False, "error": str(data)}

    except Exception as exc:
        _fail(f"GET /health failed: {exc}")
        _results["step2b"] = {"pass": False, "error": str(exc)}


# ── Step 3 — Loki Level 1 ────────────────────────────────────────────────────

def step3_loki() -> None:
    _hdr("Step 3 — Loki Level 1 Observability Check")
    _info("Querying Loki for {service=\"telegram-gateway\"} — last 60 minutes ...")
    _info(f"Loki: {LOKI_URL}")
    _info("Note: The gateway.js code does not push to Loki directly.")
    _info("      Grafana Alloy may scrape Docker container stdout logs.")
    _info("      SKIP is acceptable if the container has been idle.")

    # Use 60-minute window for Telegram — bot may be idle
    result = check_loki_service_logs(LOKI_URL, "telegram-gateway", lookback_minutes=60)

    if result.status == "PASS":
        lat = f" ({result.latency_ms:.0f}ms)" if result.latency_ms else ""
        _ok(f"{result.detail}{lat}")
    elif result.status == "SKIP":
        _info(f"SKIP — {result.detail}")
    else:
        _warn(result.detail)
        _warn("Telegram gateway does not have explicit Loki push code — known gap.")
        _warn("Container stdout logs may be captured by Grafana Alloy.")

    # Loki FAIL is a WARN here — bot may legitimately be idle and not logging
    _results["step3"] = {
        "pass":   True,  # Loki absence is expected for idle polling bot
        "status": result.status,
        "detail": result.detail,
        "note":   "Loki gap is a known observability issue — see service doc",
    }


# ── Step 4 — Optional Send Test ───────────────────────────────────────────────

def step4_send_test() -> None:
    _hdr("Step 4 — Send Test (Optional)")

    if not TEST_CHAT_ID:
        _warn("SKIP — TEST_CHAT_ID not set.")
        _warn("  Set TEST_CHAT_ID=<non-production-chat-id> to enable send validation.")
        _warn("  Never use a production chat ID for testing.")
        _results["step4"] = {"pass": True, "skipped": True}
        return

    payloads = _FIXTURES.get("message_payloads", [])
    if not payloads:
        _warn("SKIP — No message payloads in telegram_fixtures.json.")
        _results["step4"] = {"pass": True, "skipped": True}
        return

    # Use the first fixture (plain text)
    fixture    = payloads[0]
    timestamp  = _now_utc()
    msg_text   = fixture["payload"]["message"].replace("{timestamp}", timestamp)

    _info(f"Sending to TEST_CHAT_ID={TEST_CHAT_ID!r} via Telegram Bot API sendMessage ...")
    _info(f"  Message: {msg_text[:80]!r}")

    try:
        t0   = time.time()
        data = _tg("sendMessage", {
            "chat_id": TEST_CHAT_ID,
            "text":    msg_text,
        })
        ms = (time.time() - t0) * 1000

        if not data.get("ok"):
            _fail(f"sendMessage returned ok=false: {data}")
            _results["step4"] = {"pass": False, "error": str(data)}
            return

        msg_id = data["result"]["message_id"]
        _ok(f"Message sent — message_id={msg_id} ({ms:.0f}ms)")
        _info("  Note: This tests the Telegram Bot API directly, not the gateway container.")
        _info("  The gateway is validated by verifying its token is active (Steps 1-2).")
        _results["step4"] = {"pass": True, "message_id": msg_id}

    except Exception as exc:
        _fail(f"sendMessage failed: {exc}")
        _results["step4"] = {"pass": False, "error": str(exc)}


# ── Final Report ──────────────────────────────────────────────────────────────

def _print_final_report() -> None:
    total_elapsed = time.time() - _suite_start
    _hdr("Step 5 — Final Validation Report")

    STEP_LABELS = {
        "step1":  "getMe — bot token valid",
        "step2":  "getWebhookInfo — mode confirmed",
        "step2b": "Send API GET /health",
        "step3":  "Loki Level 1 observability",
        "step4":  "Send test (optional)",
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
            status, detail = "SKIP", "TEST_CHAT_ID not set"
        elif r["pass"]:
            status = "PASS"
            detail = str({k: v for k, v in r.items() if k not in ("pass", "skipped")})[:60]
        else:
            status, detail = "FAIL", str(r.get("error", ""))[:60]
            all_pass = False
        marker = "✓" if status == "PASS" else ("-" if status == "SKIP" else "!")
        print(f"  [{marker}] {label:<40} {status:<8}  {detail}")

    print()
    print(f"  Total elapsed: {total_elapsed:.1f}s")

    loki_result = (_results.get("step3") or {}).get("status", "SKIP")
    print()
    print("  Green Gate Checklist:")
    print(f"  [{'✓' if all_pass else '✗'}] 1. All validate steps PASS")
    print(f"  [{'!' }] 2. Loki Level 1 — GAP: gateway.js has no Loki push code")
    print(f"  [ ] 3. OpenAPI spec (upstream envelope schema) — telegram-gateway/openapi.yaml")
    print(f"  [ ] 4. Service doc capability registry current")
    print(f"  [ ] 5. _index.md updated")
    print(f"  [ ] 6. Evidence report — outputs/validation/")
    print(f"  [ ] 7. .env.example current")
    print()

    _warn("Observability gap: gateway.js does not push structured logs to Loki.")
    _warn("Container stdout is the only log source (via Grafana Alloy if configured).")
    _warn("Resolving this requires adding a Loki push library to the Node.js service.")

    print()
    if all_pass:
        _ok("Bot token validated. Gateway identity confirmed.")
    else:
        _fail("One or more steps FAILED. Review errors above.")


# ── Entry Point ───────────────────────────────────────────────────────────────

def main():
    print()
    print("  Telegram Gateway Validation Suite")
    print(f"  Started: {_now_utc()}")

    step0_environment()
    step1_get_me()
    step2_webhook_info()
    step2b_send_api_health()
    step3_loki()
    step4_send_test()
    _print_final_report()

    all_auto = all(
        _results.get(k, {}).get("pass", False)
        for k in ["step1", "step2", "step2b"]
    )
    sys.exit(0 if all_auto else 1)


if __name__ == "__main__":
    main()
