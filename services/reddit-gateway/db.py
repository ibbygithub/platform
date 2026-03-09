"""
Database helpers for the Reddit Gateway.
Target: platform_v1, schema: reddit
User: reddit_app
"""
import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

log = logging.getLogger("reddit_db")

PG_CONFIG = {
    "host":            os.getenv("PGHOST",     "dbnode-01"),
    "port":            int(os.getenv("PGPORT", "5432")),
    "dbname":          os.getenv("PGDATABASE", "platform_v1"),
    "user":            os.getenv("PGUSER",     "reddit_app"),
    "password":        os.getenv("PGPASSWORD", ""),
    "connect_timeout": 10,
}

# Persistence is silently disabled when PGPASSWORD is not set.
# Service continues to function as a pass-through without storing results.
PERSIST_ENABLED = bool(PG_CONFIG["password"])


def get_conn() -> Optional[Any]:
    """Open a new psycopg2 connection. Returns None if persistence is disabled."""
    if not PERSIST_ENABLED:
        return None
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        conn.autocommit = False
        return conn
    except Exception as exc:
        log.warning("DB connect failed (persistence skipped): %s", exc)
        return None


def _safe_exec(conn, sql: str, params: tuple) -> None:
    """Execute a write; commit or rollback silently — never raises."""
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        log.warning("DB write failed: %s", exc)


# ── Cache helpers ──────────────────────────────────────────────────────────────

def make_cache_key(params: Dict[str, Any]) -> str:
    """Stable hash of query parameters — used as the cache lookup key."""
    payload = json.dumps(params, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def is_cached(conn, key: str, ttl_hours: float = 1.0) -> bool:
    """Return True if this key was fetched within the TTL window."""
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT last_fetched_at FROM reddit.query_cache WHERE cache_key = %s",
                (key,),
            )
            row = cur.fetchone()
        if not row:
            return False
        age_hours = (time.time() - row[0].timestamp()) / 3600
        return age_hours < ttl_hours
    except Exception as exc:
        log.warning("Cache check failed: %s", exc)
        return False


def mark_cached(conn, key: str, count: int) -> None:
    _safe_exec(
        conn,
        """INSERT INTO reddit.query_cache (cache_key, last_fetched_at, result_count)
           VALUES (%s, NOW(), %s)
           ON CONFLICT (cache_key) DO UPDATE
             SET last_fetched_at = NOW(),
                 result_count    = EXCLUDED.result_count""",
        (key, count),
    )


def get_cached_posts(conn, key: str) -> List[Dict[str, Any]]:
    """Return posts that were stored for a given cache key."""
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT id, subreddit, title, selftext, url, author, score,
                          upvote_ratio, num_comments, permalink, is_self, created_utc
                   FROM reddit.posts
                   WHERE query_used = %s
                   ORDER BY score DESC
                   LIMIT 100""",
                (key,),
            )
            return [dict(r) for r in cur.fetchall()]
    except Exception as exc:
        log.warning("Cache read failed: %s", exc)
        return []


# ── Post / comment persistence ─────────────────────────────────────────────────

def upsert_post(
    conn,
    post:       Dict[str, Any],
    query_used: Optional[str],
    embedding:  Optional[List[float]],
) -> None:
    emb_json = json.dumps(embedding) if embedding else None
    _safe_exec(
        conn,
        """INSERT INTO reddit.posts
               (id, subreddit, title, selftext, url, author, score,
                upvote_ratio, num_comments, permalink, is_self,
                created_utc, query_used, embedding_json, embedding)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)
           ON CONFLICT (id) DO UPDATE SET
               score        = EXCLUDED.score,
               num_comments = EXCLUDED.num_comments,
               fetched_at   = NOW(),
               query_used   = COALESCE(EXCLUDED.query_used, reddit.posts.query_used),
               embedding    = COALESCE(EXCLUDED.embedding, reddit.posts.embedding)""",
        (
            post["id"], post["subreddit"], post["title"],
            post.get("selftext", ""), post["url"], post["author"],
            post["score"], post["upvote_ratio"], post["num_comments"],
            post["permalink"], post["is_self"], post["created_utc"],
            query_used, emb_json, emb_json,
        ),
    )


def upsert_comment(
    conn,
    comment:   Dict[str, Any],
    post_id:   str,
    embedding: Optional[List[float]],
) -> None:
    emb_json = json.dumps(embedding) if embedding else None
    _safe_exec(
        conn,
        """INSERT INTO reddit.comments
               (id, post_id, author, body, score, created_utc, embedding_json, embedding)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s::vector)
           ON CONFLICT (id) DO UPDATE SET
               score      = EXCLUDED.score,
               fetched_at = NOW(),
               embedding  = COALESCE(EXCLUDED.embedding, reddit.comments.embedding)""",
        (
            comment["id"], post_id, comment["author"],
            comment.get("body", ""), comment["score"],
            comment["created_utc"], emb_json, emb_json,
        ),
    )


def upsert_subreddit(conn, info: Dict[str, Any]) -> None:
    _safe_exec(
        conn,
        """INSERT INTO reddit.subreddits
               (name, title, description, subscribers, active_users, over18, created_utc)
           VALUES (%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (name) DO UPDATE SET
               subscribers  = EXCLUDED.subscribers,
               active_users = EXCLUDED.active_users,
               fetched_at   = NOW()""",
        (
            info["name"], info["title"], info["description"],
            info["subscribers"], info["active_users"],
            info["over18"], info["created_utc"],
        ),
    )


# ── Semantic search ────────────────────────────────────────────────────────────

def semantic_search(
    conn,
    vector: List[float],
    limit:  int = 10,
) -> List[Dict[str, Any]]:
    """Cosine similarity search over stored post embeddings (pgvector)."""
    if not conn:
        return []
    try:
        vec_str = "[" + ",".join(str(v) for v in vector) + "]"
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT id, subreddit, title, selftext, url, author,
                          score, permalink, created_utc,
                          1 - (embedding <=> %s::vector) AS similarity
                   FROM reddit.posts
                   WHERE embedding IS NOT NULL
                   ORDER BY embedding <=> %s::vector
                   LIMIT %s""",
                (vec_str, vec_str, limit),
            )
            return [dict(r) for r in cur.fetchall()]
    except Exception as exc:
        log.warning("Semantic search failed: %s", exc)
        return []


# ── Feed management ────────────────────────────────────────────────────────────

def get_feeds(conn) -> List[Dict[str, Any]]:
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM reddit.feeds ORDER BY id")
            return [dict(r) for r in cur.fetchall()]
    except Exception as exc:
        log.warning("get_feeds failed: %s", exc)
        return []


def create_feed(
    conn,
    subreddit:    str,
    query:        Optional[str],
    sort:         str,
    time_filter:  str,
    limit_per_run: int,
    cron_expr:    str,
) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO reddit.feeds
                   (subreddit, query, sort, time_filter, limit_per_run, cron_expr)
               VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
            (subreddit, query, sort, time_filter, limit_per_run, cron_expr),
        )
        row = dict(cur.fetchone())
    conn.commit()
    return row


def delete_feed(conn, feed_id: int) -> bool:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM reddit.feeds WHERE id = %s", (feed_id,))
        deleted = cur.rowcount
    conn.commit()
    return deleted > 0


def update_feed_run(conn, feed_id: int, count: int) -> None:
    _safe_exec(
        conn,
        "UPDATE reddit.feeds SET last_run_at = NOW(), last_run_count = %s WHERE id = %s",
        (count, feed_id),
    )
