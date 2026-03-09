"""
Platform Reddit Gateway v2
--------------------------
Reads Reddit via the public JSON API — no OAuth credentials required.
All retrieved posts and comments are persisted to platform_v1.reddit schema
with pgvector embeddings for semantic search.

Endpoints:
  GET  /health
  POST /v1/reddit/search                 Search posts (Unicode/kanji supported)
  POST /v1/reddit/subreddit/posts        Browse subreddit listings
  GET  /v1/reddit/post/{id}              Fetch full post + comments
  GET  /v1/reddit/subreddit/{name}/info  Subreddit metadata
  POST /v1/reddit/saved/search           Semantic search over stored posts
  POST /v1/reddit/feeds                  Register a scheduled feed
  GET  /v1/reddit/feeds                  List all scheduled feeds
  DELETE /v1/reddit/feeds/{id}           Remove a scheduled feed
"""
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Literal, Optional

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import db
import embeddings
import reddit_client
import scheduler

# ── Config ─────────────────────────────────────────────────────────────────────

REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "ibbytech-platform-reddit-gateway/2.0")
LOKI_URL          = os.getenv("LOKI_URL", "http://192.168.71.220:3100")
CACHE_TTL_HOURS   = float(os.getenv("CACHE_TTL_HOURS", "1.0"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
log = logging.getLogger("reddit_gateway")

reddit_client.set_user_agent(REDDIT_USER_AGENT)


# ── Loki logging ───────────────────────────────────────────────────────────────

def _loki(level: str, msg: str, **labels: str) -> None:
    """Push a structured log line to Loki. Never raises."""
    stream: Dict[str, str] = {"service": "reddit-gateway", "level": level, "node": "svcnode-01"}
    stream.update({k: str(v) for k, v in labels.items() if v is not None})
    try:
        requests.post(
            f"{LOKI_URL}/loki/api/v1/push",
            json={"streams": [{"stream": stream, "values": [[str(time.time_ns()), msg]]}]},
            timeout=3,
        )
    except Exception:
        pass


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(application: FastAPI):
    scheduler.start()
    yield
    scheduler.stop()


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Platform Reddit Gateway",
    version="2.0.0",
    lifespan=lifespan,
)


# ── Models ─────────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query:       str
    subreddit:   Optional[str]                                                        = None
    sort:        Optional[Literal["relevance", "hot", "top", "new", "comments"]]     = "relevance"
    time_filter: Optional[Literal["all", "day", "hour", "month", "week", "year"]]    = "all"
    limit:       Optional[int]                                                        = Field(default=25, ge=1, le=100)


class SubredditPostsRequest(BaseModel):
    subreddit:   str
    sort:        Optional[Literal["hot", "new", "top", "rising"]]                    = "hot"
    time_filter: Optional[Literal["all", "day", "hour", "month", "week", "year"]]    = "week"
    limit:       Optional[int]                                                        = Field(default=25, ge=1, le=100)


class SemanticSearchRequest(BaseModel):
    query: str
    limit: Optional[int] = Field(default=10, ge=1, le=50)


class FeedCreateRequest(BaseModel):
    subreddit:     str
    query:         Optional[str]                                                      = None
    sort:          Optional[Literal["hot", "new", "top", "rising", "relevance"]]     = "top"
    time_filter:   Optional[Literal["all", "day", "hour", "month", "week", "year"]]  = "week"
    limit_per_run: Optional[int]                                                      = Field(default=25, ge=1, le=100)
    cron_expr:     str = Field(description="Cron expression e.g. '0 2 * * *' (UTC)")


# ── Internal helpers ───────────────────────────────────────────────────────────

def _persist_posts(
    conn,
    posts:     List[Dict[str, Any]],
    cache_key: Optional[str] = None,
) -> None:
    """
    Embed and upsert a list of posts.
    Non-fatal — individual failures are logged and skipped.
    Comments are not fetched here (would cost one request per post);
    they are only persisted when a specific post is fetched via GET /v1/reddit/post/{id}.
    """
    for post in posts:
        embed_text = f"{post['title']} {post.get('selftext', '')}".strip()
        vector     = embeddings.embed_text(embed_text)
        db.upsert_post(conn, post, query_used=cache_key, embedding=vector)


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> Dict[str, Any]:
    db_ok = False
    if db.PERSIST_ENABLED:
        try:
            conn = db.get_conn()
            if conn:
                conn.close()
                db_ok = True
        except Exception:
            pass

    return {
        "ok":              True,
        "time":            int(time.time()),
        "version":         "2.0.0",
        "persist_enabled": db.PERSIST_ENABLED,
        "db_connected":    db_ok,
        "embed_provider":  embeddings.EMBED_PROVIDER,
        "embed_model":     embeddings.EMBED_MODEL,
        "cache_ttl_hours": CACHE_TTL_HOURS,
        "user_agent":      REDDIT_USER_AGENT,
    }


@app.post("/v1/reddit/search")
def search(req: SearchRequest) -> Dict[str, Any]:
    """
    Search Reddit posts by keyword.
    Full Unicode supported — kanji, Arabic, Cyrillic, etc.
    Results are cached for CACHE_TTL_HOURS and always persisted to Postgres.
    """
    t0          = time.time()
    status_code = "200"
    try:
        key  = db.make_cache_key({"op": "search", **req.model_dump()})
        conn = db.get_conn()

        if conn and db.is_cached(conn, key, CACHE_TTL_HOURS):
            posts = db.get_cached_posts(conn, key)
            conn.close()
            return {"ok": True, "from_cache": True, "count": len(posts), "posts": posts}

        try:
            posts = reddit_client.search(
                query       = req.query,
                subreddit   = req.subreddit,
                sort        = req.sort or "relevance",
                time_filter = req.time_filter or "all",
                limit       = req.limit or 25,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Reddit API error: {exc}")

        if conn:
            _persist_posts(conn, posts, cache_key=key)
            db.mark_cached(conn, key, len(posts))
            conn.close()

        return {"ok": True, "from_cache": False, "count": len(posts), "posts": posts}

    except HTTPException as exc:
        status_code = str(exc.status_code)
        raise
    except Exception as exc:
        status_code = "500"
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        latency = int((time.time() - t0) * 1000)
        _loki(
            "error" if status_code != "200" else "info",
            f"POST /v1/reddit/search q={req.query!r} -> {status_code} {latency}ms",
            endpoint="/v1/reddit/search", status_code=status_code,
            latency_ms=str(latency), query=req.query,
            subreddit=req.subreddit or "all",
        )


@app.post("/v1/reddit/subreddit/posts")
def subreddit_posts(req: SubredditPostsRequest) -> Dict[str, Any]:
    """Browse subreddit listings (hot / new / top / rising). Results cached and persisted."""
    t0          = time.time()
    status_code = "200"
    try:
        key  = db.make_cache_key({"op": "subreddit_posts", **req.model_dump()})
        conn = db.get_conn()

        if conn and db.is_cached(conn, key, CACHE_TTL_HOURS):
            posts = db.get_cached_posts(conn, key)
            conn.close()
            return {"ok": True, "from_cache": True, "count": len(posts), "posts": posts}

        try:
            posts = reddit_client.subreddit_posts(
                subreddit   = req.subreddit,
                sort        = req.sort or "hot",
                time_filter = req.time_filter or "week",
                limit       = req.limit or 25,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Reddit API error: {exc}")

        if conn:
            _persist_posts(conn, posts, cache_key=key)
            db.mark_cached(conn, key, len(posts))
            conn.close()

        return {"ok": True, "from_cache": False, "count": len(posts), "posts": posts}

    except HTTPException as exc:
        status_code = str(exc.status_code)
        raise
    except Exception as exc:
        status_code = "500"
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        latency = int((time.time() - t0) * 1000)
        _loki(
            "error" if status_code != "200" else "info",
            f"POST /v1/reddit/subreddit/posts r/{req.subreddit} -> {status_code} {latency}ms",
            endpoint="/v1/reddit/subreddit/posts", status_code=status_code,
            latency_ms=str(latency), subreddit=req.subreddit,
        )


@app.get("/v1/reddit/post/{post_id}")
def get_post(post_id: str, comment_limit: int = 20) -> Dict[str, Any]:
    """Fetch a single post with top-level comments. Both post and comments are persisted."""
    t0          = time.time()
    status_code = "200"
    try:
        try:
            post = reddit_client.get_post(post_id, comment_limit=comment_limit)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Reddit API error: {exc}")

        conn = db.get_conn()
        if conn:
            embed_text = f"{post['title']} {post.get('selftext', '')}".strip()
            vector     = embeddings.embed_text(embed_text)
            db.upsert_post(conn, post, query_used=None, embedding=vector)
            for comment in post.get("comments", []):
                c_vector = embeddings.embed_text(comment.get("body", ""))
                db.upsert_comment(conn, comment, post_id=post["id"], embedding=c_vector)
            conn.close()

        return {"ok": True, "post": post}

    except HTTPException as exc:
        status_code = str(exc.status_code)
        raise
    except Exception as exc:
        status_code = "500"
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        latency = int((time.time() - t0) * 1000)
        _loki(
            "error" if status_code != "200" else "info",
            f"GET /v1/reddit/post/{post_id} -> {status_code} {latency}ms",
            endpoint="/v1/reddit/post", status_code=status_code, latency_ms=str(latency),
        )


@app.get("/v1/reddit/subreddit/{name}/info")
def subreddit_info(name: str) -> Dict[str, Any]:
    """Fetch and persist subreddit metadata."""
    t0          = time.time()
    status_code = "200"
    try:
        try:
            info = reddit_client.subreddit_info(name)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Reddit API error: {exc}")

        conn = db.get_conn()
        if conn:
            db.upsert_subreddit(conn, info)
            conn.close()

        return {"ok": True, "subreddit": info}

    except HTTPException as exc:
        status_code = str(exc.status_code)
        raise
    except Exception as exc:
        status_code = "500"
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        latency = int((time.time() - t0) * 1000)
        _loki(
            "error" if status_code != "200" else "info",
            f"GET /v1/reddit/subreddit/{name}/info -> {status_code} {latency}ms",
            endpoint="/v1/reddit/subreddit/info", status_code=status_code,
            latency_ms=str(latency),
        )


@app.post("/v1/reddit/saved/search")
def saved_search(req: SemanticSearchRequest) -> Dict[str, Any]:
    """
    Semantic similarity search over posts already stored in Postgres.
    Uses pgvector cosine distance — no Reddit API call, purely local.
    Useful for agents doing research over previously collected data.
    """
    t0          = time.time()
    status_code = "200"
    try:
        conn = db.get_conn()
        if not conn:
            raise HTTPException(status_code=503, detail="DB persistence not enabled")

        vector = embeddings.embed_text(req.query)
        if not vector:
            raise HTTPException(status_code=502, detail="Embedding service unavailable")

        results = db.semantic_search(conn, vector, limit=req.limit or 10)
        conn.close()

        return {"ok": True, "query": req.query, "count": len(results), "posts": results}

    except HTTPException as exc:
        status_code = str(exc.status_code)
        raise
    except Exception as exc:
        status_code = "500"
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        latency = int((time.time() - t0) * 1000)
        _loki(
            "error" if status_code != "200" else "info",
            f"POST /v1/reddit/saved/search q={req.query!r} -> {status_code} {latency}ms",
            endpoint="/v1/reddit/saved/search", status_code=status_code,
            latency_ms=str(latency),
        )


# ── Feed management ────────────────────────────────────────────────────────────

@app.post("/v1/reddit/feeds", status_code=201)
def create_feed(req: FeedCreateRequest) -> Dict[str, Any]:
    """Register a new scheduled collection feed."""
    conn = db.get_conn()
    if not conn:
        raise HTTPException(status_code=503, detail="DB persistence not enabled")
    try:
        feed = db.create_feed(
            conn,
            subreddit     = req.subreddit,
            query         = req.query,
            sort          = req.sort or "top",
            time_filter   = req.time_filter or "week",
            limit_per_run = req.limit_per_run or 25,
            cron_expr     = req.cron_expr,
        )
        return {"ok": True, "feed": feed}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()


@app.get("/v1/reddit/feeds")
def list_feeds() -> Dict[str, Any]:
    """List all registered scheduled feeds."""
    conn = db.get_conn()
    if not conn:
        raise HTTPException(status_code=503, detail="DB persistence not enabled")
    try:
        feeds = db.get_feeds(conn)
        return {"ok": True, "count": len(feeds), "feeds": feeds}
    finally:
        conn.close()


@app.delete("/v1/reddit/feeds/{feed_id}")
def delete_feed(feed_id: int) -> Dict[str, Any]:
    """Remove a scheduled feed by ID."""
    conn = db.get_conn()
    if not conn:
        raise HTTPException(status_code=503, detail="DB persistence not enabled")
    try:
        deleted = db.delete_feed(conn, feed_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Feed {feed_id} not found")
        return {"ok": True, "deleted_id": feed_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()
