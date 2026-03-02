# LLM Gateway

Provider-agnostic HTTP gateway for LLM operations. Single API for embeddings and chat across OpenAI, Google Gemini, and Anthropic Claude. Callers choose the provider per request or rely on environment defaults.

## Endpoints

| FQDN | Purpose |
|------|---------|
| `llm.platform.ibbytech.com` | LLM chat and embeddings gateway |

## Quick Start

```bash
cp .env.example .env    # fill in at least one provider API key
docker compose up --build -d
curl https://llm.platform.ibbytech.com/health
```

FastAPI auto-docs: `https://llm.platform.ibbytech.com/docs`

## API

### `GET /health`
Shows which providers have keys configured and current defaults.

### `POST /v1/chat`
```json
{
  "provider": "anthropic",
  "model": "claude-sonnet-4-6",
  "messages": [
    { "role": "system", "content": "You are a concise assistant." },
    { "role": "user",   "content": "What should I eat near Dotonbori?" }
  ],
  "temperature": 0.3,
  "max_output_tokens": 512
}
```
Returns: `{ "provider": "anthropic", "model": "...", "output_text": "...", "usage": {...} }`

### `POST /v1/embeddings`
```json
{
  "provider": "openai",
  "model": "text-embedding-3-small",
  "input": ["the best ramen in Osaka", "late night noodles"]
}
```
Returns: `{ "provider": "openai", "model": "...", "vectors": [[...], [...]], "usage": {...} }`

Note: Anthropic does not provide an embeddings API. Requests to `provider: "anthropic"` on `/v1/embeddings` return a `400` error.

## Provider Reference

| Provider | Chat models | Embed models |
|----------|-------------|--------------|
| `openai` | gpt-4o, gpt-4o-mini | text-embedding-3-small, text-embedding-3-large |
| `google` | gemini-2.0-flash, gemini-2.0-pro | text-embedding-004, embedding-001 |
| `anthropic` | claude-opus-4-6, claude-sonnet-4-6, claude-haiku-4-5-20251001 | — |
