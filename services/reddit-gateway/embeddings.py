"""
Embedding helper — calls the platform LLM Gateway.
Mirrors the scraper service pattern exactly.
"""
import logging
import os
from typing import List, Optional

import requests

log = logging.getLogger("reddit_embed")

LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://platform-llm-gateway:8080").rstrip("/")
EMBED_PROVIDER  = os.getenv("EMBED_PROVIDER",  "openai")
EMBED_MODEL     = os.getenv("EMBED_MODEL",     "text-embedding-3-small")
EMBED_MAX_CHARS = 8000


def embed_text(text: str) -> Optional[List[float]]:
    """
    Embed text via the LLM Gateway. Returns None on any failure —
    the caller continues without an embedding rather than failing the request.
    """
    if not text or not LLM_GATEWAY_URL:
        return None
    try:
        r = requests.post(
            f"{LLM_GATEWAY_URL}/v1/embeddings",
            json={
                "provider": EMBED_PROVIDER,
                "model":    EMBED_MODEL,
                "input":    [text[:EMBED_MAX_CHARS]],
            },
            timeout=30,
        )
        if r.status_code == 200:
            vectors = r.json().get("vectors", [])
            return vectors[0] if vectors else None
        log.warning("LLM Gateway embedding returned %s: %s", r.status_code, r.text[:200])
    except Exception as exc:
        log.warning("Embedding failed (stored without vector): %s", exc)
    return None
