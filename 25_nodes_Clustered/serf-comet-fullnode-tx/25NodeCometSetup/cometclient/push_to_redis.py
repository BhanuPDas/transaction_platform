import logging
import json
import redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)
rd = redis.Redis(host='localhost', port=6379, decode_responses=True)
lq_channel = "liqo:initiate"
em_Channel = "emulate"


def publish_to_liqo(buyer_obj, seller_obj, amount, tx_start_ts, lease_duration):
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
        rd.publish(lq_channel, msg)
        logger.info(f"Message has been published to Redis: {msg}")
    except Exception as e:
        logger.error(f"Received error while publishing to redis: {e}")


def publish_to_emulate(tx_details):
    logger.info("Preparing records to publish to emulate..")
    try:
        msg = json.dumps(tx_details)
        rd.publish(em_Channel, msg)
        logger.info(f"Message has been published to Emulate Redis: {msg}")
    except Exception as e:
        logger.error(f"Received error while publishing to redis: {e}")
