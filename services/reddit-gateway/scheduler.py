"""
Background scheduler for Reddit feed collection.

Uses APScheduler with a single interval job that fires every FEED_INTERVAL_HOURS.
On each tick it loads all enabled feeds from Postgres and runs them sequentially,
respecting the global rate limiter in reddit_client.

Feed cron_expr values are stored in Postgres as documentation of intended frequency.
All feeds run on the same global interval — per-feed cron scheduling is a future enhancement.
"""
import logging
import os
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

log = logging.getLogger("reddit_scheduler")

FEED_INTERVAL_HOURS = float(os.getenv("FEED_INTERVAL_HOURS", "6"))

_scheduler: Optional[BackgroundScheduler] = None


def _run_all_feeds() -> None:
    """
    Load all enabled feeds from DB and execute each one.
    Runs in the scheduler background thread — must not raise.
    """
    import db
    import embeddings
    import reddit_client

    conn = db.get_conn()
    if not conn:
        log.warning("Scheduler: no DB connection, skipping feed run")
        return

    feeds = db.get_feeds(conn)
    conn.close()

    enabled = [f for f in feeds if f.get("enabled")]
    log.info("Scheduler tick: %d enabled feeds to run", len(enabled))

    for feed in enabled:
        feed_conn = db.get_conn()
        count     = 0
        try:
            log.info(
                "Running feed id=%s r/%s query=%s sort=%s",
                feed["id"], feed["subreddit"], feed.get("query"), feed.get("sort"),
            )

            if feed.get("query"):
                posts = reddit_client.search(
                    query       = feed["query"],
                    subreddit   = feed["subreddit"] or None,
                    sort        = feed.get("sort", "top"),
                    time_filter = feed.get("time_filter", "week"),
                    limit       = feed.get("limit_per_run", 25),
                )
            else:
                posts = reddit_client.subreddit_posts(
                    subreddit   = feed["subreddit"],
                    sort        = feed.get("sort", "top"),
                    time_filter = feed.get("time_filter", "week"),
                    limit       = feed.get("limit_per_run", 25),
                )

            for post in posts:
                embed_text = f"{post['title']} {post.get('selftext', '')}".strip()
                vector     = embeddings.embed_text(embed_text)
                db.upsert_post(feed_conn, post, query_used=None, embedding=vector)
                count += 1

            db.update_feed_run(feed_conn, feed["id"], count)
            log.info("Feed id=%s complete — %d posts saved", feed["id"], count)

        except Exception as exc:
            log.error("Feed id=%s failed: %s", feed["id"], exc)
        finally:
            if feed_conn:
                feed_conn.close()


def start() -> None:
    """Start the background scheduler. Call once at application startup."""
    global _scheduler
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _run_all_feeds,
        trigger="interval",
        hours=FEED_INTERVAL_HOURS,
        id="feed_runner",
        # First run 60 seconds after startup — lets the service fully initialise
        # and the DB connection stabilise before hitting Reddit.
        next_run_time=None,
    )
    # Schedule the first run 60s from now using a one-shot date trigger
    from datetime import datetime, timedelta, timezone
    from apscheduler.triggers.date import DateTrigger
    first_run = datetime.now(timezone.utc) + timedelta(seconds=60)
    _scheduler.add_job(
        _run_all_feeds,
        trigger=DateTrigger(run_date=first_run),
        id="feed_runner_initial",
    )
    _scheduler.start()
    log.info(
        "Scheduler started — feeds run every %.1fh (first run in 60s)",
        FEED_INTERVAL_HOURS,
    )


def stop() -> None:
    """Shut down the scheduler gracefully."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        log.info("Scheduler stopped")
