#!/usr/bin/env python3
"""
validate_llm_gateway.py
Phase 0: LLM gateway API and container audit.

Run from: C:/git/work/platform/tools/dashboard/

Required env vars:
  LLM_GATEWAY_KEY  -- API key for gateway auth (Part A authenticated calls)
  LLM_GATEWAY_URL  -- optional override (default: https://llm.platform.ibbytech.com)
"""

import os
import subprocess
import sys
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

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

TIMEOUT     = 20  # seconds -- longer budget for LLM inference calls
GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "https://llm.platform.ibbytech.com").rstrip("/")
# No bearer token -- the gateway is open internally; auth is handled by the
# provider keys (OPENAI_API_KEY etc.) baked into the container env.
SSH_KEY     = os.path.expanduser("~/.ssh/devops-agent_ed25519_clean")
SSH_TARGET  = "devops-agent@192.168.71.220"


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str
    latency_ms: Optional[float] = None
    extra: Optional[str] = None  # supplemental detail printed on a second line


HEADERS = {"Content-Type": "application/json"}

# -- Part A helpers ------------------------------------------------------------

def check_health() -> CheckResult:
    # GET /health -- no auth, returns provider key status
    try:
        start = time.monotonic()
        resp = requests.get(f"{GATEWAY_URL}/health", timeout=TIMEOUT, verify=False)
        latency = (time.monotonic() - start) * 1000
        if resp.status_code == 200:
            data = resp.json()
            providers = data.get("providers", {})
            defaults  = data.get("defaults", {})
            detail = (
                f"HTTP 200 -- "
                f"openai={'yes' if providers.get('openai_key_set') else 'NO'} "
                f"google={'yes' if providers.get('google_key_set') else 'NO'} "
                f"anthropic={'yes' if providers.get('anthropic_key_set') else 'NO'} | "
                f"default chat: {defaults.get('chat', {}).get('provider')}/{defaults.get('chat', {}).get('model')} "
                f"embed: {defaults.get('embed', {}).get('provider')}/{defaults.get('embed', {}).get('model')}"
            )
            all_keys = all([
                providers.get("openai_key_set"),
                providers.get("google_key_set"),
                providers.get("anthropic_key_set"),
            ])
            return CheckResult("/health endpoint", all_keys, detail, latency)
        return CheckResult("/health endpoint", False, f"HTTP {resp.status_code}: {resp.text[:200]}", latency)
    except requests.exceptions.ConnectionError:
        return CheckResult("/health endpoint", False, "Connection refused / DNS error")
    except requests.exceptions.Timeout:
        return CheckResult("/health endpoint", False, f"Timeout after {TIMEOUT}s")
    except Exception as e:
        return CheckResult("/health endpoint", False, str(e))


def check_completion() -> CheckResult:
    # POST /v1/chat -- gateway's native chat endpoint (not /v1/chat/completions)
    payload = {
        "messages": [{"role": "user", "content": "Reply with exactly the word: GATEWAY_OK"}],
        "max_output_tokens": 20,
        # omit provider/model to exercise defaults (google/gemini-2.0-flash)
    }
    try:
        start = time.monotonic()
        resp = requests.post(
            f"{GATEWAY_URL}/v1/chat",
            headers=HEADERS, json=payload,
            timeout=TIMEOUT, verify=False,
        )
        latency = (time.monotonic() - start) * 1000
        if resp.status_code == 200:
            data    = resp.json()
            text    = data.get("output_text", "").strip()
            model   = data.get("model", "unknown")
            provider = data.get("provider", "unknown")
            return CheckResult(
                "/v1/chat (default provider)", True,
                f"HTTP 200 -- {provider}/{model}", latency,
                extra=f"Response: {text!r}",
            )
        return CheckResult("/v1/chat (default provider)", False,
                           f"HTTP {resp.status_code}: {resp.text[:200]}", latency)
    except (KeyError, IndexError) as e:
        return CheckResult("/v1/chat (default provider)", False, f"Unexpected response shape: {e}")
    except Exception as e:
        return CheckResult("/v1/chat (default provider)", False, str(e))


def check_streaming() -> CheckResult:
    # The gateway has no streaming endpoint -- document this accurately
    return CheckResult(
        "Streaming support", False,
        "Not implemented -- /v1/chat returns full response only (no SSE/stream param)",
        extra="Dashboard will use non-streaming calls. This is expected, not a failure.",
    )


def check_embeddings() -> CheckResult:
    # POST /v1/embeddings -- input is a list of strings, returns vectors list
    payload = {
        "input": ["platform validation test"],
        # omit provider/model to use defaults (openai/text-embedding-3-small)
    }
    try:
        start = time.monotonic()
        resp = requests.post(
            f"{GATEWAY_URL}/v1/embeddings",
            headers=HEADERS, json=payload,
            timeout=TIMEOUT, verify=False,
        )
        latency = (time.monotonic() - start) * 1000
        if resp.status_code == 200:
            data    = resp.json()
            vectors = data.get("vectors", [])
            dims    = len(vectors[0]) if vectors else 0
            model   = data.get("model", "unknown")
            return CheckResult("/v1/embeddings", True,
                               f"HTTP 200 -- {dims} dimensions, model: {model}", latency)
        return CheckResult("/v1/embeddings", False,
                           f"HTTP {resp.status_code}: {resp.text[:200]}", latency)
    except Exception as e:
        return CheckResult("/v1/embeddings", False, str(e))


# -- Part B helpers ------------------------------------------------------------

def _ssh(command: str) -> tuple[bool, str]:
    """Run a command on svcnode-01 as devops-agent. Returns (success, output)."""
    cmd = [
        "ssh", "-i", SSH_KEY,
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        SSH_TARGET,
        command,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "SSH command timed out after 30s"
    except Exception as e:
        return False, str(e)


def check_container_running() -> CheckResult:
    ok, output = _ssh(
        "docker ps --filter name=llm-gateway --format '{{.Names}}\\t{{.Status}}\\t{{.Image}}'"
    )
    if not ok:
        return CheckResult("Container running", False, f"SSH error: {output}")
    if not output:
        return CheckResult("Container running", False,
                           "No container matching 'llm-gateway' found in docker ps")
    return CheckResult("Container running", True, output)


def check_env_vars() -> CheckResult:
    # Get container ID first, then inspect env -- mask secret values
    ok, output = _ssh(
        "docker inspect "
        "--format '{{range .Config.Env}}{{println .}}{{end}}' "
        "$(docker ps -qf name=llm-gateway) 2>/dev/null"
    )
    if not ok or not output:
        return CheckResult("Environment vars", False,
                           f"Could not inspect container env: {output}")

    lines = output.splitlines()
    found_openai    = any(l.startswith("OPENAI_API_KEY=")    for l in lines)
    found_anthropic = any(l.startswith("ANTHROPIC_API_KEY=") for l in lines)

    details = []
    details.append("OPENAI_API_KEY=*** (present)" if found_openai    else "OPENAI_API_KEY -- NOT FOUND")
    details.append("ANTHROPIC_API_KEY=*** (present)" if found_anthropic else "ANTHROPIC_API_KEY -- not present")

    # Minimum: OPENAI_API_KEY must be present for completions to work
    return CheckResult("Environment vars", found_openai, " | ".join(details))


def check_recent_logs() -> CheckResult:
    ok, output = _ssh(
        "docker logs --tail 50 $(docker ps -qf name=llm-gateway) 2>&1"
    )
    if not ok:
        return CheckResult("Recent logs (tail 50)", False, f"SSH/logs error: {output}")

    lines  = output.splitlines()
    errors = [l for l in lines if any(kw in l for kw in ("ERROR", "FATAL", "Exception", "Traceback"))]

    if errors:
        return CheckResult(
            "Recent logs (tail 50)", False,
            f"{len(errors)} error line(s) in last {len(lines)} log lines",
            extra="\n          ".join(errors[:5]),
        )
    return CheckResult("Recent logs (tail 50)", True,
                       f"No ERROR/FATAL in last {len(lines)} log lines")


# -- Output --------------------------------------------------------------------

def print_section(title: str, results: list[CheckResult]) -> None:
    print(f"\n{BOLD}{title}{RESET}")
    print(f"{'-' * 80}")
    for r in results:
        status     = f"{GREEN}PASS{RESET}" if r.passed else f"{RED}FAIL{RESET}"
        latency_s  = f" ({r.latency_ms:.0f}ms)" if r.latency_ms is not None else ""
        print(f"  {status}  {r.name:<32} {r.detail}{latency_s}")
        if r.extra:
            print(f"          {YELLOW}{r.extra}{RESET}")


def main() -> None:
    print(f"\n{BOLD}IbbyTech Platform -- LLM Gateway Validation{RESET}")
    print(f"Date:    {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Gateway: {GATEWAY_URL}")
    print(f"Auth:    none (gateway is open internally -- no bearer token required)")
    print(f"SSH key: {SSH_KEY}")

    # Part A -- HTTP from laptop
    part_a: list[CheckResult] = [
        check_health(),
        check_completion(),
        check_streaming(),
        check_embeddings(),
    ]
    print_section("Part A -- HTTP checks from laptop", part_a)

    # Part B -- SSH container inspection via devops-agent
    part_b: list[CheckResult] = [
        check_container_running(),
        check_env_vars(),
        check_recent_logs(),
    ]
    print_section("Part B -- SSH container inspection (devops-agent -> svcnode-01)", part_b)

    # Summary
    all_results = part_a + part_b
    passed = [r for r in all_results if r.passed]
    failed = [r for r in all_results if not r.passed]

    print(f"\n{'-' * 80}")
    print(f"Result: {len(passed)}/{len(all_results)} checks passed")

    if failed:
        print(f"\n{RED}{BOLD}Failed checks:{RESET}")
        for r in failed:
            print(f"  {RED}*{RESET} {r.name}: {r.detail}")
        llm_critical = any(r.name in ("/health endpoint", "/v1/chat (default provider)") for r in failed)
        if llm_critical:
            print(f"\n{RED}CRITICAL: LLM gateway health or chat completion failing.")
            print(f"Do not proceed to Phase 1 until resolved.{RESET}\n")
        else:
            print(f"\n{YELLOW}Non-critical failures noted -- review before Phase 1.{RESET}\n")
    else:
        print(f"\n{GREEN}{BOLD}All checks passed. LLM gateway ready for Phase 1.{RESET}\n")

    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
