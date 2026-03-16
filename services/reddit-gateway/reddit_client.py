"""
Reddit public JSON API client with self-imposed rate limiting.
No credentials required — uses public unauthenticated endpoints.
Rate ceiling: 50 requests per 60 seconds (token bucket).
"""
import logging
import threading
import time
from typing import Any, Dict, List, Optional

import requests

log = logging.getLogger("reddit_client")

REDDIT_BASE  = "https://www.reddit.com"
_user_agent  = "ibbytech-platform-reddit-gateway/2.0"  # overridden from env at startup


class _TokenBucket:
    """Thread-safe token bucket — N tokens refilled per 60 seconds."""

    def __init__(self, rate: int = 50, per: float = 60.0) -> None:
        self._rate   = float(rate)
        self._per    = per
        self._tokens = float(rate)
        self._last   = time.monotonic()
        self._lock   = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now            = time.monotonic()
            elapsed        = now - self._last
            self._last     = now
            self._tokens   = min(self._rate, self._tokens + elapsed * self._rate / self._per)
            if self._tokens < 1.0:
                wait = (1.0 - self._tokens) * self._per / self._rate
                time.sleep(wait)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0


_limiter = _TokenBucket(rate=50, per=60.0)


def set_user_agent(ua: str) -> None:
    global _user_agent
    _user_agent = ua


def _get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Rate-limited GET to Reddit public JSON API. Backs off on 429."""
    _limiter.acquire()
    headers = {"User-Agent": _user_agent, "Accept": "application/json"}
    r = requests.get(path, params=params, headers=headers, timeout=15)
    if r.status_code == 429:
        log.warning("Reddit 429 received — backing off 30s and retrying")
        time.sleep(30)
        _limiter.acquire()
        r = requests.get(path, params=params, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()


# ── Formatters ────────────────────────────────────────────────────────────────

def _fmt_post(child: Dict[str, Any]) -> Dict[str, Any]:
    d = child.get("data", {})
    return {
        "id":           d.get("id", ""),
        "title":        d.get("title", ""),
        "subreddit":    d.get("subreddit", ""),
        "author":       d.get("author") or "[deleted]",
        "score":        d.get("score", 0),
        "upvote_ratio": d.get("upvote_ratio", 0.0),
        "num_comments": d.get("num_comments", 0),
        "url":          d.get("url", ""),
        "permalink":    f"https://reddit.com{d.get('permalink', '')}",
        "selftext":     (d.get("selftext") or "")[:3000],
        "created_utc":  d.get("created_utc", 0.0),
        "is_self":      bool(d.get("is_self")),
    }


def _fmt_comment(child: Dict[str, Any]) -> Dict[str, Any]:
    d = child.get("data", {})
    return {
        "id":          d.get("id", ""),
        "author":      d.get("author") or "[deleted]",
        "body":        (d.get("body") or "")[:2000],
        "score":       d.get("score", 0),
        "created_utc": d.get("created_utc", 0.0),
    }


# ── Public API ────────────────────────────────────────────────────────────────

def search(
    query:       str,
    subreddit:   Optional[str] = None,
    sort:        str = "relevance",
    time_filter: str = "all",
    limit:       int = 25,
) -> List[Dict[str, Any]]:
    """
    Search Reddit posts. Supports full Unicode including kanji.
    If subreddit is provided, restricts search to that community.
    """
    path   = f"{REDDIT_BASE}/r/{subreddit}/search.json" if subreddit else f"{REDDIT_BASE}/search.json"
    params: Dict[str, Any] = {
        "q":    query,
        "sort": sort,
        "t":    time_filter,
        "limit": min(limit, 100),
        "type": "link",
    }
    if subreddit:
        params["restrict_sr"] = 1

    data     = _get(path, params)
    children = data.get("data", {}).get("children", [])
    return [_fmt_post(c) for c in children if c.get("kind") == "t3"]


def subreddit_posts(
    subreddit:   str,
    sort:        str = "hot",
    time_filter: str = "week",
    limit:       int = 25,
) -> List[Dict[str, Any]]:
    """Browse subreddit listings (hot / new / top / rising)."""
    path   = f"{REDDIT_BASE}/r/{subreddit}/{sort}.json"
    params: Dict[str, Any] = {"limit": min(limit, 100)}
    if sort == "top":
        params["t"] = time_filter

    data     = _get(path, params)
    children = data.get("data", {}).get("children", [])
    return [_fmt_post(c) for c in children if c.get("kind") == "t3"]


def get_post(post_id: str, comment_limit: int = 20) -> Dict[str, Any]:
    """Fetch a single post with its top-level comments."""
    path = f"{REDDIT_BASE}/comments/{post_id}.json"
    data = _get(path, {"limit": comment_limit, "depth": 1})

    post          = _fmt_post(data[0]["data"]["children"][0])
    comment_kids  = data[1]["data"]["children"] if len(data) > 1 else []
    post["comments"] = [
        _fmt_comment(c) for c in comment_kids if c.get("kind") == "t1"
    ][:comment_limit]
    return post


def subreddit_info(name: str) -> Dict[str, Any]:
    """Fetch subreddit metadata."""
    path = f"{REDDIT_BASE}/r/{name}/about.json"
    data = _get(path, {})
    d    = data.get("data", {})
    return {
        "name":         d.get("display_name", name),
        "title":        d.get("title", ""),
        "description":  (d.get("public_description") or "")[:500],
        "subscribers":  d.get("subscribers", 0),
        "active_users": d.get("accounts_active", 0),
        "over18":       bool(d.get("over18")),
        "created_utc":  d.get("created_utc", 0.0),
    }
