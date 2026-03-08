"""
txlog.py
Transaction logger for the IbbyTech Platform Dashboard.

Appends one JSON line per operation to dashboard_transactions.log.
Each record carries: timestamp, tab, operation, latency_ms, request
payload, response payload (with smart truncation), and any error.

Usage:
    import txlog
    with txlog.Tx("scraper", "scrape") as tx:
        tx.req({"url": url})
        result = do_work()
        tx.resp(result)
    # record written on __exit__
"""

import json
import math
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

LOG_FILE = Path(__file__).parent / "dashboard_transactions.log"

# ---------------------------------------------------------------------------
# Truncation helpers
# ---------------------------------------------------------------------------

def _trunc_str(s: str, limit: int = 1000) -> str:
    if not isinstance(s, str):
        s = str(s)
    if len(s) <= limit:
        return s
    return s[:limit] + f"  … [{len(s) - limit} more chars]"


def _trunc_vector(v: list) -> dict:
    """Summarise an embedding vector without logging all 1536 floats."""
    if not v:
        return {"dim": 0, "preview": []}
    dim = len(v)
    preview = [round(x, 6) for x in v[:5]]
    norm = round(math.sqrt(sum(x * x for x in v)), 6)
    return {"dim": dim, "preview": preview, "l2_norm": norm, "note": f"[{dim - 5} values omitted]"}


def _trunc_value(v: Any, key: str = "") -> Any:
    """Recursively truncate a value for log-safe serialisation."""
    if isinstance(v, str):
        # Long text fields — markdown, content, raw HTML, chunk_text
        if key in ("markdown", "content", "html", "chunk_text", "raw", "combined_markdown"):
            return _trunc_str(v, 1000)
        if key in ("answer", "output_text"):
            return _trunc_str(v, 800)
        # Message content inside LLM payloads
        if key == "content" and len(v) > 500:
            return _trunc_str(v, 500)
        return v

    if isinstance(v, list):
        # Detect embedding vector: list of floats
        if v and isinstance(v[0], float) and len(v) > 10:
            return _trunc_vector(v)
        # Vectors nested inside a list-of-lists (batch embeddings)
        if v and isinstance(v[0], list) and v[0] and isinstance(v[0][0], float):
            return [_trunc_vector(vec) for vec in v]
        return [_trunc_value(item, key) for item in v]

    if isinstance(v, dict):
        return {k: _trunc_value(val, k) for k, val in v.items()}

    return v


# ---------------------------------------------------------------------------
# Core writer
# ---------------------------------------------------------------------------

def _write(record: dict) -> None:
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # never let logging crash the request


# ---------------------------------------------------------------------------
# Context-manager API
# ---------------------------------------------------------------------------

class Tx:
    """
    Context manager that times a dashboard operation and writes one log record.

        with txlog.Tx("scraper", "scrape") as tx:
            tx.req({"url": url, ...})
            result = call_service()
            tx.resp(result)
    """

    def __init__(self, tab: str, operation: str):
        self.tab       = tab
        self.operation = operation
        self._start    = None
        self._request  = {}
        self._response = {}
        self._error    = None
        self._subs: list[dict] = []   # nested sub-calls (LLM, embed, etc.)

    def req(self, data: dict) -> None:
        self._request = data

    def resp(self, data: Any) -> None:
        self._response = data

    def error(self, msg: str) -> None:
        self._error = msg

    def sub(self, label: str, data: dict) -> None:
        """Log a nested sub-call (e.g. LLM summary, embedding request)."""
        self._subs.append({"sub": label, **data})

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        latency_ms = round((time.monotonic() - self._start) * 1000)

        if exc_val and not self._error:
            self._error = str(exc_val)

        record: dict[str, Any] = {
            "ts":         time.strftime("%Y-%m-%dT%H:%M:%S"),
            "tab":        self.tab,
            "op":         self.operation,
            "latency_ms": latency_ms,
            "ok":         self._error is None,
        }
        if self._request:
            record["request"] = _trunc_value(self._request)
        if self._response:
            record["response"] = _trunc_value(self._response)
        if self._subs:
            record["sub_calls"] = [_trunc_value(s) for s in self._subs]
        if self._error:
            record["error"] = self._error

        _write(record)
        return False  # do not suppress exceptions


# ---------------------------------------------------------------------------
# /api/transactions reader
# ---------------------------------------------------------------------------

def read_transactions(limit: int = 20, tab: str | None = None) -> list[dict]:
    """Read the last `limit` records from the log, newest first, optionally filtered by tab."""
    if not LOG_FILE.exists():
        return []
    try:
        lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []

    records: list[dict] = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if tab and r.get("tab") != tab:
            continue
        records.append(r)
        if len(records) >= limit:
            break

    return records
