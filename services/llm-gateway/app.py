import os
import time
from typing import Any, Dict, List, Literal, Optional

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ---- OpenAI ----
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

# ---- Google Gemini ----
GOOGLE_API_KEY  = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_BASE_URL = os.getenv("GOOGLE_BASE_URL", "https://generativelanguage.googleapis.com").rstrip("/")

# ---- Anthropic Claude ----
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
ANTHROPIC_VERSION  = "2023-06-01"

# ---- Defaults ----
DEFAULT_EMBED_PROVIDER = os.getenv("DEFAULT_EMBED_PROVIDER", "openai")
DEFAULT_EMBED_MODEL    = os.getenv("DEFAULT_EMBED_MODEL",    "text-embedding-3-small")
DEFAULT_CHAT_PROVIDER  = os.getenv("DEFAULT_CHAT_PROVIDER",  "google")
DEFAULT_CHAT_MODEL     = os.getenv("DEFAULT_CHAT_MODEL",     "gemini-2.0-flash")

Provider = Literal["openai", "google", "anthropic"]

app = FastAPI(title="Platform LLM Gateway", version="0.2.0")


# ===== Auth guard =====

def _require_key(provider: str) -> None:
    if provider == "openai"    and not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set")
    if provider == "google"    and not GOOGLE_API_KEY:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY is not set")
    if provider == "anthropic" and not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY is not set")


# ===== Pydantic models =====

class EmbeddingsRequest(BaseModel):
    provider: Optional[Provider] = Field(default=None, description="openai|google  (anthropic has no embeddings API)")
    model:    Optional[str]      = Field(default=None)
    input:    List[str]          = Field(..., description="List of texts to embed")
    metadata: Optional[Dict[str, Any]] = None


class EmbeddingsResponse(BaseModel):
    provider: Provider
    model:    str
    vectors:  List[List[float]]
    usage:    Dict[str, Any]


class ChatMessage(BaseModel):
    role:    Literal["system", "user", "assistant"]
    content: str


class MultimodalRequest(BaseModel):
    """
    Single-turn multimodal request (Google Gemini only).
    Used by shogun-core for voice transcription and photo analysis.
    """
    model:             Optional[str]  = None
    prompt:            str                        # Text instruction
    file_data:         str                        # Base64-encoded file bytes
    mime_type:         str                        # e.g. audio/ogg, image/jpeg
    system_prompt:     Optional[str]  = None
    temperature:       Optional[float] = 0.1
    max_output_tokens: Optional[int]   = 2000


class MultimodalResponse(BaseModel):
    provider:    str
    model:       str
    output_text: str
    usage:       Dict[str, Any]


class ChatRequest(BaseModel):
    provider:          Optional[Provider]        = None
    model:             Optional[str]             = None
    messages:          List[ChatMessage]
    temperature:       Optional[float]           = 0.2
    max_output_tokens: Optional[int]             = 1024
    metadata:          Optional[Dict[str, Any]]  = None


class ChatResponse(BaseModel):
    provider:    Provider
    model:       str
    output_text: str
    usage:       Dict[str, Any]


# ===== Health =====

@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok":   True,
        "time": int(time.time()),
        "providers": {
            "openai_key_set":    bool(OPENAI_API_KEY),
            "google_key_set":    bool(GOOGLE_API_KEY),
            "anthropic_key_set": bool(ANTHROPIC_API_KEY),
        },
        "defaults": {
            "embed": {"provider": DEFAULT_EMBED_PROVIDER, "model": DEFAULT_EMBED_MODEL},
            "chat":  {"provider": DEFAULT_CHAT_PROVIDER,  "model": DEFAULT_CHAT_MODEL},
        },
    }


# ===== Embedding providers =====

def _openai_embeddings(model: str, texts: List[str]) -> Dict[str, Any]:
    url     = f"{OPENAI_BASE_URL}/embeddings"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json={"model": model, "input": texts}, timeout=60)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail={"provider": "openai", "status": r.status_code, "body": r.text})
    return r.json()


def _google_embeddings(model: str, texts: List[str]) -> Dict[str, Any]:
    if not model.startswith("models/"):
        model = f"models/{model}"
    url     = f"{GOOGLE_BASE_URL}/v1beta/{model}:batchEmbedContents?key={GOOGLE_API_KEY}"
    payload = {"requests": [{"model": model, "content": {"parts": [{"text": t}]}} for t in texts]}
    r = requests.post(url, json=payload, timeout=60)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail={"provider": "google", "status": r.status_code, "body": r.text})
    return r.json()


# ===== Chat providers =====

def _openai_chat(model: str, messages: List[ChatMessage], temperature: float, max_output_tokens: int) -> Dict[str, Any]:
    url     = f"{OPENAI_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model":      model,
        "messages":   [m.model_dump() for m in messages],
        "temperature": temperature,
        "max_tokens":  max_output_tokens,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=120)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail={"provider": "openai", "status": r.status_code, "body": r.text})
    return r.json()


def _google_chat(model: str, messages: List[ChatMessage], temperature: float, max_output_tokens: int) -> Dict[str, Any]:
    system_parts = [m.content for m in messages if m.role == "system"]
    user_parts   = [f"{m.role.upper()}: {m.content}" for m in messages if m.role != "system"]
    system_instruction = "\n\n".join(system_parts).strip() if system_parts else None
    user_text          = "\n\n".join(user_parts).strip()

    if not model.startswith("models/"):
        model = f"models/{model}"

    url     = f"{GOOGLE_BASE_URL}/v1beta/{model}:generateContent?key={GOOGLE_API_KEY}"
    payload: Dict[str, Any] = {
        "contents":         [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_output_tokens},
    }
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    r = requests.post(url, json=payload, timeout=120)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail={"provider": "google", "status": r.status_code, "body": r.text})
    return r.json()


def _anthropic_chat(model: str, messages: List[ChatMessage], temperature: float, max_output_tokens: int) -> Dict[str, Any]:
    system_parts  = [m.content for m in messages if m.role == "system"]
    chat_messages = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]

    url     = f"{ANTHROPIC_BASE_URL}/v1/messages"
    headers = {
        "x-api-key":         ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type":      "application/json",
    }
    payload: Dict[str, Any] = {
        "model":      model,
        "messages":   chat_messages,
        "max_tokens": max_output_tokens,
        "temperature": temperature,
    }
    if system_parts:
        payload["system"] = "\n\n".join(system_parts)

    r = requests.post(url, headers=headers, json=payload, timeout=120)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail={"provider": "anthropic", "status": r.status_code, "body": r.text})
    return r.json()


# ===== Routes =====

@app.post("/v1/embeddings", response_model=EmbeddingsResponse)
def embeddings(req: EmbeddingsRequest) -> EmbeddingsResponse:
    provider: Provider = (req.provider or DEFAULT_EMBED_PROVIDER)  # type: ignore
    model              = req.model or DEFAULT_EMBED_MODEL
    _require_key(provider)

    if provider == "anthropic":
        raise HTTPException(status_code=400, detail="Anthropic does not provide an embeddings API. Use openai or google.")

    if provider == "openai":
        raw     = _openai_embeddings(model, req.input)
        vectors = [item["embedding"] for item in raw.get("data", [])]
        usage   = raw.get("usage", {}) or {}
        return EmbeddingsResponse(provider="openai", model=model, vectors=vectors, usage=usage)

    if provider == "google":
        raw             = _google_embeddings(model, req.input)
        embeddings_list = raw.get("embeddings") or []
        vectors         = [e.get("values", []) for e in embeddings_list]
        usage           = raw.get("usageMetadata", {}) or {"note": "usageMetadata may vary by model"}
        return EmbeddingsResponse(provider="google", model=model, vectors=vectors, usage=usage)

    raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")


@app.post("/v1/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    provider: Provider = (req.provider or DEFAULT_CHAT_PROVIDER)  # type: ignore
    model              = req.model or DEFAULT_CHAT_MODEL
    _require_key(provider)

    temperature       = float(req.temperature or 0.2)
    max_output_tokens = int(req.max_output_tokens or 1024)

    if provider == "openai":
        raw     = _openai_chat(model, req.messages, temperature, max_output_tokens)
        choices = raw.get("choices", [])
        text    = (choices[0].get("message", {}) or {}).get("content", "") if choices else ""
        usage   = raw.get("usage", {}) or {}
        return ChatResponse(provider="openai", model=model, output_text=text, usage=usage)

    if provider == "google":
        raw        = _google_chat(model, req.messages, temperature, max_output_tokens)
        candidates = raw.get("candidates", [])
        parts      = (((candidates[0].get("content") or {}).get("parts")) or []) if candidates else []
        text       = parts[0].get("text", "") if parts else ""
        usage      = raw.get("usageMetadata", {}) or {"note": "usageMetadata may vary by model"}
        return ChatResponse(provider="google", model=model, output_text=text, usage=usage)

    if provider == "anthropic":
        raw     = _anthropic_chat(model, req.messages, temperature, max_output_tokens)
        content = raw.get("content", [])
        text    = content[0].get("text", "") if content else ""
        usage   = raw.get("usage", {}) or {}
        return ChatResponse(provider="anthropic", model=model, output_text=text, usage=usage)

    raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")


@app.post("/v1/multimodal", response_model=MultimodalResponse)
def multimodal(req: MultimodalRequest) -> MultimodalResponse:
    """
    Single-turn multimodal completion via Google Gemini.
    Accepts a base64-encoded file (audio or image) plus a text prompt.
    Returns output_text — the model's response to the prompt about the file.

    Use cases:
      - Voice transcription: mime_type=audio/ogg, prompt="Transcribe this voice message."
      - Photo analysis: mime_type=image/jpeg, prompt="Describe what you see in this image."
    """
    _require_key("google")
    model = req.model or DEFAULT_CHAT_MODEL
    if not model.startswith("models/"):
        model = f"models/{model}"

    parts: List[Dict[str, Any]] = [
        {"inline_data": {"mime_type": req.mime_type, "data": req.file_data}},
        {"text": req.prompt},
    ]
    payload: Dict[str, Any] = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature":     float(req.temperature or 0.1),
            "maxOutputTokens": int(req.max_output_tokens or 2000),
        },
    }
    if req.system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": req.system_prompt}]}

    url = f"{GOOGLE_BASE_URL}/v1beta/{model}:generateContent?key={GOOGLE_API_KEY}"
    r = requests.post(url, json=payload, timeout=120)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail={"provider": "google", "status": r.status_code, "body": r.text})

    raw        = r.json()
    candidates = raw.get("candidates", [])
    parts_out  = (((candidates[0].get("content") or {}).get("parts")) or []) if candidates else []
    text       = parts_out[0].get("text", "") if parts_out else ""
    usage      = raw.get("usageMetadata", {}) or {}

    return MultimodalResponse(provider="google", model=model, output_text=text.strip(), usage=usage)
