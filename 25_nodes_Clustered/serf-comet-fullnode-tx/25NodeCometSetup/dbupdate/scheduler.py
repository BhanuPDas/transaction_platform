"""
scheduler.py
Background job: finds tx_history rows with status='ongoing' whose
tx_end_unix has passed, marks them 'Completed', and updates the
tx_msg JSON payload's status/tx_end_ts fields in place.

Runs on an interval via APScheduler, in a background thread of the
same process as Flask (single worker -- see Dockerfile).
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler

import db

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "900"))
BATCH_SIZE = int(os.environ.get("JOB_BATCH_SIZE", "700"))

ONGOING_STATUS = "OnGoing"
COMPLETED_STATUS = "Completed"


def _update_tx_msg(tx_msg_raw, current_ts, row_id):
    """Parse tx_msg, set status/tx_end_ts, return new JSON string (or None)."""
    try:
        payload = tx_msg_raw if isinstance(tx_msg_raw, dict) else json.loads(tx_msg_raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        logger.warning("Unparsable tx_msg, skipping row", extra={"id": row_id})
        return None, None

    tx_hash = payload.get("tx_hash")
    payload["status"] = COMPLETED_STATUS
    payload["tx_end_ts"] = current_ts
    new_str = json.dumps(payload)

    if len(new_str) > 1200:
        logger.warning(
            "Updated tx_msg exceeds 1200 char column limit",
            extra={"id": row_id, "tx_hash": tx_hash, "length": len(new_str)},
        )
    return new_str, tx_hash


def job_tick():
    """One scheduler tick: process all currently-expired ongoing transactions."""
    current_unix = int(time.time())
    current_ts = datetime.now(timezone.utc).isoformat()
    start = time.monotonic()

    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, uuid, tx_msg
                    FROM public.tx_history
                    WHERE status = %s AND tx_end_unix <= %s
                    ORDER BY id
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED;
                    """,
                    (ONGOING_STATUS, current_unix, BATCH_SIZE),
                )
                rows = cur.fetchall()

                updated = 0
                for row_id, row_uuid, tx_msg_raw in rows:
                    new_tx_msg, tx_hash = _update_tx_msg(tx_msg_raw, current_ts, row_id)
                    if new_tx_msg is None:
                        continue

                    cur.execute(
                        """
                        UPDATE public.tx_history
                        SET status = %s, tx_msg = %s, last_updated = %s
                        WHERE id = %s;
                        """,
                        (COMPLETED_STATUS, new_tx_msg, current_ts, row_id),
                    )
                    updated += 1
                    logger.info(
                        "Transaction completed",
                        extra={"id": row_id, "uuid": row_uuid, "tx_hash": tx_hash},
                    )

                conn.commit()

        elapsed_ms = round((time.monotonic() - start) * 1000, 1)
        if rows:
            logger.info(
                "Tick complete",
                extra={"found": len(rows), "updated": updated, "elapsed_ms": elapsed_ms},
            )
        else:
            logger.debug("Tick complete: nothing expired", extra={"elapsed_ms": elapsed_ms})

    except Exception:
        logger.exception("Tick failed; will retry next interval")


_scheduler = None


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        job_tick,
        trigger="interval",
        seconds=POLL_INTERVAL_SECONDS,
        id="tx_history_expiry_job",
        max_instances=1,   # never overlap ticks
        coalesce=True,     # collapse missed ticks into one
        next_run_time=datetime.now(timezone.utc),  # run immediately on startup
    )
    _scheduler.start()
    logger.info("Scheduler started", extra={"poll_interval_seconds": POLL_INTERVAL_SECONDS})
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")
