import logging
import json
import redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)
rd = redis.Redis(host='localhost', port=6379, decode_responses=True)
channel = "liqo:initiate"


def publish_redis(buyer_obj, seller_obj, amount, tx_start_ts, lease_duration):
    logger.info("Preparing records to publish to redis..")
    tx = {
        "type": "transfer",
        "buyer": buyer_obj,
        "seller": seller_obj,
        "amount": amount,
        "tx_start_ts": tx_start_ts,
        "lease_duration": lease_duration
    }
    try:
        msg = json.dumps(tx)
        rd.publish(channel, msg)
        logger.info(f"Message has been published to Redis: {msg}")
    except Exception as e:
        logger.error(f"Received error while publishing to redis: {e}")
