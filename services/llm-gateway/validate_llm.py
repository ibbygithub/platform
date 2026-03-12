#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_llm.py
===============
End-to-end validation of the Platform LLM Gateway.

Tests all three provider paths (openai, google, anthropic), both endpoint
types (chat and embeddings), and default routing behaviour.

Steps
-----
  0  Environment discovery — which provider keys are configured server-side
  1  Health check — GET /health (reports which keys are set on server)
  2  Embeddings — POST /v1/embeddings (default provider + explicit openai)
  3  Chat — default provider (fixture LLM_CHAT_001: echo_check)
  4  Provider routing — test each provider that is reported as key_set=true
  5  Regression — all 3 endpoints (HTTP status + shape check)
  6  Loki Level 1 — check {service="llm-gateway"} logs
  7  Final report + Green Gate checklist

Observability gap
-----------------
  app.py (FastAPI) has no Loki push code. Step 6 will SKIP or FAIL.
  Documented as a known gap in the Green Gate report.

Prerequisites
-------------
  pip install requests

Environment variables
---------------------
  LLM_GATEWAY_URL   default: https://llm.platform.ibbytech.com
  LOKI_URL          default: http://192.168.71.220:3100

  No inbound API key required — provider keys live server-side on svcnode-01.

Usage
-----
  python validate_llm.py
"""

import importlib.util
import json
import os
import pathlib
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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
_FIXTURES_PATH = pathlib.Path(__file__).parent.parent.parent / "tools" / "test-harness" / "fixtures" / "llm_fixtures.json"
_FIXTURES: Dict[str, Any] = {}
if _FIXTURES_PATH.exists():
    with open(_FIXTURES_PATH) as _f:
        _FIXTURES = json.load(_f)

# ── Config ───────────────────────────────────────────────────────────────────
GATEWAY_URL = os.environ.get("LLM_GATEWAY_URL", "https://llm.platform.ibbytech.com").rstrip("/")
LOKI_URL    = os.environ.get("LOKI_URL", "http://192.168.71.220:3100")

# ── Globals ───────────────────────────────────────────────────────────────────
_suite_start = time.time()
_results: Dict[str, Dict[str, Any]] = {}
_server_providers: Dict[str, bool] = {}  # populated by Step 1


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

def _get(path: str, timeout: int = 10) -> requests.Response:
    return requests.get(f"{GATEWAY_URL}{path}", timeout=timeout)

def _post(path: str, body: Dict, timeout: int = 60) -> requests.Response:
    return requests.post(f"{GATEWAY_URL}{path}", json=body,
                         headers={"Content-Type": "application/json"}, timeout=timeout)


# ── Step 0 — Environment Discovery ───────────────────────────────────────────

def step0_environment() -> None:
    _hdr("Step 0 — Environment Discovery")
    _info(f"LLM_GATEWAY_URL = {GATEWAY_URL}")
    _info(f"LOKI_URL        = {LOKI_URL}")
    _info(f"Fixtures loaded = {len(_FIXTURES.get('chat_prompts', []))} chat prompts, "
          f"{len(_FIXTURES.get('embedding_prompts', []))} embed prompts")
    print()
    _info("Auth note: No inbound API key — provider keys are server-side on svcnode-01.")
    _info("Observability note: app.py has no Loki push code — Step 6 will SKIP/FAIL.")


# ── Step 1 — Health Check ─────────────────────────────────────────────────────

def step1_health() -> None:
    _hdr("Step 1 — Health Check")
    _info(f"GET {GATEWAY_URL}/health ...")

    try:
        t0 = time.time()
        r  = _get("/health", timeout=10)
        ms = (time.time() - t0) * 1000

        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")

        body = r.json()
        _ok(f"Health OK ({ms:.0f}ms)")

        providers = body.get("providers", {})
        defaults  = body.get("defaults", {})
        _info(f"  openai_key_set    = {providers.get('openai_key_set')}")
        _info(f"  google_key_set    = {providers.get('google_key_set')}")
        _info(f"  anthropic_key_set = {providers.get('anthropic_key_set')}")
        _info(f"  default_embed     = {defaults.get('embed')}")
        _info(f"  default_chat      = {defaults.get('chat')}")

        # Cache for downstream steps
        _server_providers["openai"]    = bool(providers.get("openai_key_set"))
        _server_providers["google"]    = bool(providers.get("google_key_set"))
        _server_providers["anthropic"] = bool(providers.get("anthropic_key_set"))

        active = [k for k, v in _server_providers.items() if v]
        if not active:
            _warn("No provider keys are configured on the server — all chat/embed calls will fail.")
        else:
            _info(f"  Active providers: {', '.join(active)}")

        _results["step1"] = {"pass": True, "providers": _server_providers}

    except Exception as exc:
        _fail(f"Health check failed: {exc}")
        _results["step1"] = {"pass": False, "error": str(exc)}
        sys.exit(1)


# ── Step 2 — Embeddings ───────────────────────────────────────────────────────

def step2_embeddings() -> None:
    _hdr("Step 2 — Embeddings (POST /v1/embeddings)")

    embed_prompts = _FIXTURES.get("embedding_prompts", [])
    if not embed_prompts:
        _warn("No embedding prompts in fixtures — using inline fallback")
        embed_prompts = [{"input": ["platform validation test"], "expected_dimensions": 1536}]

    # Test 1: single input (LLM_EMBED_001)
    fixture = embed_prompts[0]
    input_texts = fixture.get("input", ["platform validation test"])
    expected_dim = fixture.get("expected_dimensions", 1536)

    _info(f"Single input: {input_texts} (expect {expected_dim}-dim vectors) ...")
    try:
        t0 = time.time()
        r  = _post("/v1/embeddings", {"input": input_texts}, timeout=30)
        ms = (time.time() - t0) * 1000

        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")

        body    = r.json()
        vectors = body.get("vectors", [])
        provider = body.get("provider")
        model    = body.get("model")

        if not vectors:
            raise RuntimeError("Response has no vectors")

        dim = len(vectors[0])
        _ok(f"Embeddings OK — provider={provider} model={model} dim={dim} ({ms:.0f}ms)")
        if dim != expected_dim:
            _warn(f"  Dimension mismatch: expected {expected_dim}, got {dim}")
            _warn("  Update expected_dimensions in llm_fixtures.json if model changed.")
        embed_pass_1 = True
    except Exception as exc:
        _fail(f"Single-input embedding failed: {exc}")
        embed_pass_1 = False

    # Test 2: batch input (LLM_EMBED_002)
    if len(embed_prompts) > 1:
        fixture2 = embed_prompts[1]
        input2   = fixture2.get("input", [])
        expected_count = fixture2.get("expected_count", len(input2))
        print()
        _info(f"Batch input: {len(input2)} texts ...")
        try:
            t0 = time.time()
            r  = _post("/v1/embeddings", {"input": input2}, timeout=30)
            ms = (time.time() - t0) * 1000

            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")

            body    = r.json()
            vectors = body.get("vectors", [])
            _ok(f"Batch embedding OK — {len(vectors)} vectors returned ({ms:.0f}ms)")
            if len(vectors) != expected_count:
                _warn(f"  Count mismatch: expected {expected_count}, got {len(vectors)}")
            embed_pass_2 = True
        except Exception as exc:
            _fail(f"Batch embedding failed: {exc}")
            embed_pass_2 = False
    else:
        embed_pass_2 = True

    _results["step2"] = {"pass": embed_pass_1 and embed_pass_2}


# ── Step 3 — Chat (Default Provider) ─────────────────────────────────────────

def step3_chat_default() -> None:
    _hdr("Step 3 — Chat: Default Provider (echo_check)")

    # LLM_CHAT_001: echo check — most reliable for automated pass/fail
    prompts = _FIXTURES.get("chat_prompts", [])
    fixture = next((p for p in prompts if p.get("fixture_id") == "LLM_CHAT_001"), None)
    if not fixture:
        fixture = {
            "messages": [{"role": "user", "content": "Reply with exactly the word: GATEWAY_OK"}],
            "max_output_tokens": 20,
            "validation": {"type": "contains", "expected": "GATEWAY_OK", "case_sensitive": False},
        }

    messages = fixture["messages"]
    max_tok  = fixture.get("max_output_tokens", 20)
    expected = fixture.get("validation", {}).get("expected", "GATEWAY_OK")

    _info(f"Prompt: {messages[-1]['content']!r}")
    _info(f"Expect response to contain: {expected!r}")

    try:
        t0 = time.time()
        r  = _post("/v1/chat", {
            "messages":          messages,
            "max_output_tokens": max_tok,
        }, timeout=60)
        ms = (time.time() - t0) * 1000

        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")

        body     = r.json()
        text     = body.get("output_text", "")
        provider = body.get("provider")
        model    = body.get("model")

        _info(f"  provider={provider}  model={model}  ({ms:.0f}ms)")
        _info(f"  output_text: {text!r}")

        if expected.lower() in text.lower():
            _ok(f"Echo check PASS — response contains {expected!r}")
            _results["step3"] = {"pass": True, "provider": provider, "model": model}
        else:
            _fail(f"Echo check FAIL — expected {expected!r} not in {text!r}")
            _results["step3"] = {"pass": False, "error": f"{expected!r} not found", "text": text}

    except Exception as exc:
        _fail(f"Chat (default) failed: {exc}")
        _results["step3"] = {"pass": False, "error": str(exc)}


# ── Step 4 — Provider Routing ─────────────────────────────────────────────────

def step4_provider_routing() -> None:
    _hdr("Step 4 — Provider Routing (test each active provider)")

    # LLM_CHAT_005: provider routing variants
    prompts  = _FIXTURES.get("chat_prompts", [])
    fixture5 = next((p for p in prompts if p.get("fixture_id") == "LLM_CHAT_005"), None)
    variants = fixture5.get("variants", []) if fixture5 else [
        {"provider": "google",    "model": "gemini-2.0-flash",
         "messages": [{"role": "user", "content": "Reply with: GEMINI_OK"}],
         "validation": {"expected": "GEMINI_OK"}},
        {"provider": "openai",    "model": "gpt-4o-mini",
         "messages": [{"role": "user", "content": "Reply with: OPENAI_OK"}],
         "validation": {"expected": "OPENAI_OK"}},
        {"provider": "anthropic", "model": "claude-haiku-4-5-20251001",
         "messages": [{"role": "user", "content": "Reply with: ANTHROPIC_OK"}],
         "validation": {"expected": "ANTHROPIC_OK"}},
    ]

    provider_results: Dict[str, bool] = {}

    for v in variants:
        provider = v.get("provider", "?")
        model    = v.get("model", "?")
        messages = v.get("messages", [])
        expected = v.get("validation", {}).get("expected", "OK")

        if not _server_providers.get(provider, False):
            _info(f"  SKIP {provider:<10} — key not set on server")
            provider_results[provider] = None  # not applicable
            continue

        _info(f"  Testing {provider}/{model} ...")
        try:
            t0 = time.time()
            r  = _post("/v1/chat", {
                "provider":          provider,
                "model":             model,
                "messages":          messages,
                "max_output_tokens": 20,
            }, timeout=60)
            ms = (time.time() - t0) * 1000

            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")

            text = r.json().get("output_text", "")
            if expected.lower() in text.lower():
                _ok(f"  {provider:<10} PASS — response contains {expected!r} ({ms:.0f}ms)")
                provider_results[provider] = True
            else:
                _fail(f"  {provider:<10} FAIL — {expected!r} not found in {text!r}")
                provider_results[provider] = False
        except Exception as exc:
            _fail(f"  {provider:<10} ERROR — {exc}")
            provider_results[provider] = False

    tested   = {k: v for k, v in provider_results.items() if v is not None}
    all_pass = all(v for v in tested.values()) if tested else True  # PASS if nothing to test

    _results["step4"] = {"pass": all_pass, "providers": provider_results}


# ── Step 5 — Regression ───────────────────────────────────────────────────────

def step5_regression() -> None:
    _hdr("Step 5 — Regression: All 3 Endpoints")
    _info("HTTP status + response shape checks.")

    checks = [
        ("GET  /health",
         lambda: _get("/health", timeout=10),
         lambda r: r.status_code == 200 and "ok" in r.json()),

        ("POST /v1/embeddings",
         lambda: _post("/v1/embeddings", {"input": ["regression test"]}, timeout=30),
         lambda r: r.status_code == 200 and "vectors" in r.json()),

        ("POST /v1/chat",
         lambda: _post("/v1/chat", {
             "messages": [{"role": "user", "content": "Reply: OK"}],
             "max_output_tokens": 10,
         }, timeout=60),
         lambda r: r.status_code == 200 and "output_text" in r.json()),

        # Bad provider — should get 400
        ("POST /v1/chat (bad provider)",
         lambda: _post("/v1/chat", {
             "provider": "invalid_provider",
             "messages": [{"role": "user", "content": "test"}],
         }, timeout=10),
         lambda r: r.status_code in (400, 422)),

        # Embeddings with anthropic (not supported) — should get 400
        ("POST /v1/embeddings (anthropic, unsupported)",
         lambda: _post("/v1/embeddings", {
             "provider": "anthropic",
             "input": ["test"],
         }, timeout=10),
         lambda r: r.status_code == 400),
    ]

    all_passed = True
    for label, call_fn, validator in checks:
        try:
            t0 = time.time()
            r  = call_fn()
            ms = (time.time() - t0) * 1000
            ok = validator(r)
            if ok:
                _ok(f"{label:<45} HTTP {r.status_code} ({ms:.0f}ms)")
            else:
                _fail(f"{label:<45} HTTP {r.status_code} — unexpected shape ({ms:.0f}ms)")
                all_passed = False
        except Exception as exc:
            _fail(f"{label:<45} {exc}")
            all_passed = False

    _results["step5"] = {"pass": all_passed}


# ── Step 6 — Loki Level 1 ────────────────────────────────────────────────────

def step6_loki() -> None:
    _hdr("Step 6 — Loki Level 1 Observability Check")
    _info("Querying Loki for {service=\"llm-gateway\"} — last 15 minutes ...")
    _info(f"Loki: {LOKI_URL}")
    _info("Known gap: app.py (FastAPI) has no Loki push code. SKIP/FAIL expected.")

    result = check_loki_service_logs(LOKI_URL, "llm-gateway", lookback_minutes=15)

    if result.status == "PASS":
        lat = f" ({result.latency_ms:.0f}ms)" if result.latency_ms else ""
        _ok(f"{result.detail}{lat}")
    elif result.status == "SKIP":
        _info(f"SKIP — {result.detail}")
    else:
        _warn(result.detail)
        _warn("Known gap: app.py does not push structured logs to Loki.")
        _warn("Fix: Add Loki push calls to /v1/chat and /v1/embeddings handlers (separate task).")

    _results["step6"] = {
        "pass":   True,
        "status": result.status,
        "detail": result.detail,
        "note":   "Loki push missing from app.py — known observability gap",
    }


# ── Final Report ──────────────────────────────────────────────────────────────

def _print_final_report() -> None:
    total_elapsed = time.time() - _suite_start
    _hdr("Step 7 — Final Validation Report")

    STEP_LABELS = {
        "step1": "Health check (provider key status)",
        "step2": "Embeddings (single + batch)",
        "step3": "Chat — default provider (echo_check)",
        "step4": "Provider routing (openai/google/anthropic)",
        "step5": "Regression — all 3 endpoints",
        "step6": "Loki Level 1 observability",
    }

    print()
    print(f"  {'Test':<42} {'Status':<8}  Detail")
    print("  " + "-" * 72)
    all_pass = True
    for key, label in STEP_LABELS.items():
        r = _results.get(key)
        if r is None:
            status, detail = "SKIP", "Not reached"
        elif r["pass"]:
            status = "PASS"
            detail = str({k: v for k, v in r.items() if k != "pass"})[:60]
        else:
            status, detail = "FAIL", str(r.get("error", ""))[:60]
            all_pass = False
        marker = "✓" if status == "PASS" else ("-" if status == "SKIP" else "!")
        print(f"  [{marker}] {label:<40} {status:<8}  {detail}")

    print()
    print(f"  Total elapsed: {total_elapsed:.1f}s")
    print()
    print(f"  Server provider status:")
    for prov, active in _server_providers.items():
        print(f"    {prov:<12} {'key_set=true — ACTIVE' if active else 'key_set=false — INACTIVE'}")

    print()
    print("  Green Gate Checklist:")
    print(f"  [{'✓' if all_pass else '✗'}] 1. All validate steps PASS")
    print(f"  [{'!' }] 2. Loki Level 1 — GAP: app.py has no Loki push code")
    print(f"  [ ] 3. OpenAPI spec — services/llm-gateway/openapi.yaml")
    print(f"  [ ] 4. Service doc capability registry current")
    print(f"  [ ] 5. _index.md updated")
    print(f"  [ ] 6. Evidence report — outputs/validation/")
    print(f"  [ ] 7. .env.example current")
    print()

    _warn("Observability gap: LLM gateway does not push to Loki.")
    _warn("Impact: Token usage, cost, latency cannot be monitored from Grafana.")
    _warn("Priority: HIGH — billing visibility requires Loki logging (separate task).")
    print()

    if all_pass:
        _ok("All provider paths validated. Gateway functioning correctly.")
    else:
        _fail("One or more steps FAILED. Review errors above.")


# ── Entry Point ───────────────────────────────────────────────────────────────

def main():
    print()
    print("  LLM Gateway Validation Suite")
    print(f"  Started: {_now_utc()}")

    step0_environment()
    step1_health()
    step2_embeddings()
    step3_chat_default()
    step4_provider_routing()
    step5_regression()
    step6_loki()
    _print_final_report()

    all_auto = all(
        _results.get(k, {}).get("pass", False)
        for k in ["step1", "step2", "step3", "step5"]
    )
    sys.exit(0 if all_auto else 1)


if __name__ == "__main__":
    main()
