"""
services.py
Platform service clients for the MVP dashboard.

All services are called via their internal HTTP URLs -- no API keys required
from the dashboard; keys live inside each gateway container.
"""

import os
import time
from typing import Any

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "https://llm.platform.ibbytech.com").rstrip("/")
SCRAPER_URL     = os.getenv("SCRAPER_URL",     "http://scrape.platform.ibbytech.com").rstrip("/")
PLACES_URL      = os.getenv("PLACES_URL",      "http://places.platform.ibbytech.com").rstrip("/")
TELEGRAM_URL    = os.getenv("TELEGRAM_URL",    "http://telegram.platform.ibbytech.com").rstrip("/")

HEADERS = {"Content-Type": "application/json"}


# ── LLM Gateway ───────────────────────────────────────────────────────────────

def llm_chat(messages: list[dict], max_output_tokens: int = 1024,
             provider: str | None = None, model: str | None = None) -> str:
    """Send a chat request to the LLM gateway. Returns output_text string."""
    payload: dict[str, Any] = {"messages": messages, "max_output_tokens": max_output_tokens}
    if provider:
        payload["provider"] = provider
    if model:
        payload["model"] = model

    resp = requests.post(f"{LLM_GATEWAY_URL}/v1/chat",
                         headers=HEADERS, json=payload, timeout=60, verify=False)
    resp.raise_for_status()
    return resp.json()["output_text"]


def llm_embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts via the LLM gateway. Returns list of float vectors."""
    resp = requests.post(f"{LLM_GATEWAY_URL}/v1/embeddings",
                         headers=HEADERS, json={"input": texts}, timeout=60, verify=False)
    resp.raise_for_status()
    return resp.json()["vectors"]


# ── Scraper ───────────────────────────────────────────────────────────────────

def scrape_url(url: str) -> dict:
    """Scrape a URL. Returns the data dict from the scraper response."""
    resp = requests.post(f"{SCRAPER_URL}/v1/scrape",
                         headers=HEADERS,
                         json={"url": url, "formats": ["markdown"]},
                         timeout=90)
    resp.raise_for_status()
    return resp.json().get("data", {})


# ── Places ────────────────────────────────────────────────────────────────────

def places_search(text_query: str, lat: float, lng: float,
                  radius_m: int = 5000, max_results: int = 10) -> list[dict]:
    """Search Google Places. Returns list of place dicts."""
    resp = requests.post(f"{PLACES_URL}/v1/places/search_text",
                         headers=HEADERS,
                         json={"text_query": text_query, "lat": lat, "lng": lng,
                               "radius_m": radius_m, "max_results": max_results},
                         timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("error", "Places search failed"))
    return data.get("data", {}).get("places", [])


# ── Geocoding ─────────────────────────────────────────────────────────────────

def geocode(location: str) -> tuple[float, float]:
    """Convert a location string to (lat, lng) via Nominatim (no API key required)."""
    resp = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": location, "format": "json", "limit": 1},
        headers={"User-Agent": "IbbyTech-Platform-Dashboard/1.0"},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        raise ValueError(f"Could not find location: {location!r}")
    return float(results[0]["lat"]), float(results[0]["lon"])


# ── Health checks ─────────────────────────────────────────────────────────────

def _ping(name: str, url: str, timeout: int = 5) -> dict:
    """Ping a service health endpoint. Returns a status dict."""
    try:
        start = time.monotonic()
        resp = requests.get(url, timeout=timeout, verify=False)
        latency_ms = round((time.monotonic() - start) * 1000)
        ok = resp.status_code < 500
        detail = {}
        try:
            detail = resp.json()
        except Exception:
            pass
        return {"service": name, "ok": ok, "status_code": resp.status_code,
                "latency_ms": latency_ms, "detail": detail}
    except requests.exceptions.Timeout:
        return {"service": name, "ok": False, "status_code": None,
                "latency_ms": None, "detail": {"error": "timeout"}}
    except Exception as e:
        return {"service": name, "ok": False, "status_code": None,
                "latency_ms": None, "detail": {"error": str(e)}}


def health_all() -> list[dict]:
    """Ping all platform services. Returns list of status dicts."""
    return [
        _ping("LLM Gateway",     f"{LLM_GATEWAY_URL}/health"),
        _ping("Scraper",         f"{SCRAPER_URL}/health"),
        _ping("Google Places",   f"{PLACES_URL}/health"),
        _ping("Telegram",        f"{TELEGRAM_URL}/"),
        # Reddit has no documented FQDN yet
        {"service": "Reddit Gateway", "ok": None, "status_code": None,
         "latency_ms": None, "detail": {"error": "URL not yet documented"}},
    ]
