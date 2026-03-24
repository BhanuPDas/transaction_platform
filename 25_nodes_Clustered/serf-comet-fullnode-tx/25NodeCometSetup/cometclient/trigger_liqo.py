import datetime
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


def publish_redis(buyer, buyer_ip, seller, seller_ip, cpu, ram, storage, gpu, amount, quantity):
    logger.info("Preparing records to publish to redis..")
    tx = {
        "type": "transfer",
        "from_node": buyer,
        "buyer_ip": buyer_ip,
        "to_node": seller,
        "seller_ip": seller_ip,
        "cpu": cpu,
        "ram": ram,
        "storage": storage,
        "gpu": gpu,
        "amount": amount,
        "quantity": quantity,
        "timestamp": datetime.datetime.now().isoformat()
    }
    try:
        msg = json.dumps(tx)
        rd.publish(channel, msg)
        logger.info(f"Message has been published to Redis: {msg}")
    except Exception as e:
        logger.error(f"Received error while publishing to redis: {e}")
