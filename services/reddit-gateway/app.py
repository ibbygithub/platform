import os
import time
from typing import Any, Dict, List, Literal, Optional

import praw
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

REDDIT_CLIENT_ID     = os.getenv("REDDIT_CLIENT_ID",     "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT    = os.getenv("REDDIT_USER_AGENT",    "platform-reddit-gateway/1.0")

app = FastAPI(title="Platform Reddit Gateway", version="0.1.0")


def _get_reddit() -> praw.Reddit:
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Reddit API credentials not configured (REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET)")
    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )


def _fmt_submission(s) -> Dict[str, Any]:
    return {
        "id":           s.id,
        "title":        s.title,
        "subreddit":    str(s.subreddit),
        "author":       str(s.author) if s.author else "[deleted]",
        "score":        s.score,
        "upvote_ratio": s.upvote_ratio,
        "num_comments": s.num_comments,
        "url":          s.url,
        "permalink":    f"https://reddit.com{s.permalink}",
        "selftext":     (s.selftext or "")[:2000],
        "created_utc":  s.created_utc,
        "is_self":      s.is_self,
    }


def _fmt_comment(c) -> Dict[str, Any]:
    return {
        "id":          c.id,
        "author":      str(c.author) if c.author else "[deleted]",
        "body":        (c.body or "")[:1000],
        "score":       c.score,
        "created_utc": c.created_utc,
    }


# ===== Models =====

class SearchRequest(BaseModel):
    query:       str
    subreddit:   Optional[str]                                                                 = None
    sort:        Optional[Literal["relevance", "hot", "top", "new", "comments"]]              = "relevance"
    time_filter: Optional[Literal["all", "day", "hour", "month", "week", "year"]]             = "all"
    limit:       Optional[int]                                                                 = Field(default=25, le=100)


class SubredditPostsRequest(BaseModel):
    subreddit:   str
    sort:        Optional[Literal["hot", "new", "top", "rising"]]                             = "hot"
    time_filter: Optional[Literal["all", "day", "hour", "month", "week", "year"]]             = "week"
    limit:       Optional[int]                                                                 = Field(default=25, le=100)


# ===== Routes =====

@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok":              True,
        "time":            int(time.time()),
        "credentials_set": bool(REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET),
    }


@app.post("/v1/reddit/search")
def search(req: SearchRequest) -> Dict[str, Any]:
    """Search Reddit posts by keyword, optionally scoped to a subreddit."""
    reddit = _get_reddit()
    try:
        target  = reddit.subreddit(req.subreddit) if req.subreddit else reddit.subreddit("all")
        results = target.search(req.query, sort=req.sort, time_filter=req.time_filter, limit=req.limit)
        posts   = [_fmt_submission(s) for s in results]
        return {"ok": True, "query": req.query, "subreddit": req.subreddit, "count": len(posts), "posts": posts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/reddit/subreddit/posts")
def subreddit_posts(req: SubredditPostsRequest) -> Dict[str, Any]:
    """Get hot / new / top / rising posts from a subreddit."""
    reddit = _get_reddit()
    try:
        sub = reddit.subreddit(req.subreddit)
        if req.sort == "hot":
            results = sub.hot(limit=req.limit)
        elif req.sort == "new":
            results = sub.new(limit=req.limit)
        elif req.sort == "top":
            results = sub.top(time_filter=req.time_filter, limit=req.limit)
        elif req.sort == "rising":
            results = sub.rising(limit=req.limit)
        else:
            results = sub.hot(limit=req.limit)

        posts = [_fmt_submission(s) for s in results]
        return {"ok": True, "subreddit": req.subreddit, "sort": req.sort, "count": len(posts), "posts": posts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/reddit/post/{post_id}")
def get_post(post_id: str, comment_limit: int = 20) -> Dict[str, Any]:
    """Get a single post with top-level comments."""
    reddit = _get_reddit()
    try:
        submission = reddit.submission(id=post_id)
        submission.comments.replace_more(limit=0)
        comments = [_fmt_comment(c) for c in list(submission.comments)[:comment_limit]]
        post     = _fmt_submission(submission)
        post["comments"] = comments
        return {"ok": True, "post": post}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/reddit/subreddit/{name}/info")
def subreddit_info(name: str) -> Dict[str, Any]:
    """Get basic metadata about a subreddit."""
    reddit = _get_reddit()
    try:
        sub = reddit.subreddit(name)
        return {
            "ok": True,
            "subreddit": {
                "name":             sub.display_name,
                "title":            sub.title,
                "description":      (sub.public_description or "")[:500],
                "subscribers":      sub.subscribers,
                "active_users":     sub.accounts_active,
                "over18":           sub.over18,
                "created_utc":      sub.created_utc,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
