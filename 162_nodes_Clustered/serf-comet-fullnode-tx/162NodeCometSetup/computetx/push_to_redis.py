"""
Publishes successful (OnGoing) transactions to Redis for liqo, unchanged in
spirit from the original `push_to_redis.publish_to_liqo`.
"""

from __future__ import annotations

import json
import os

import redis

LQ_CHANNEL = os.environ.get("LIQO_REDIS_CHANNEL", "liqo")
REDIS_STREAM_NAME = "emulate"
REDIS_STREAM_MAXLEN = 5000

rd = redis.Redis(
    host=os.environ.get("REDIS_HOST", "localhost"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
    db=int(os.environ.get("REDIS_DB", 0)),
    decode_responses=True,
)


def publish_to_liqo(payload: dict, logger) -> None:
    logger.info("Preparing record to publish to Redis...")
    try:
        msg = json.dumps(payload)
        rd.publish(LQ_CHANNEL, msg)
        logger.info(f"Message published to Redis channel '{LQ_CHANNEL}': {msg}")
    except Exception as exc:
        logger.error(f"Error publishing to Redis: {exc}")

def publish_ongoing_to_redis(event: dict, logger) -> None:
    tx_json = json.dumps(event)
    logger.info("Publishing to Redis emulate stream: %s", tx_json)
    try:
        rd.xadd(REDIS_STREAM_NAME, {"ongoingtx": tx_json},
            maxlen=REDIS_STREAM_MAXLEN,
            approximate=True)
    except Exception:
        logger.exception(
            "Failed publishing OnGoing tx to Redis stream=%s", REDIS_STREAM_NAME
        )
