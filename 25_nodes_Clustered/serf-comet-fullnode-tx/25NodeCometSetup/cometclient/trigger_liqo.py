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


def publish_redis(buyer, buyer_ip, seller, seller_ip, cpu, ram, storage, gpu, amount, score,
                  quantity, price, lease_duration, tx_start_ts, seller_energy, resource_type):
    logger.info("Preparing records to publish to redis..")
    tx = {
        "type": "transfer",
        "buyer": buyer,
        "buyer_ip": buyer_ip,
        "seller": seller,
        "seller_ip": seller_ip,
        "cpu": cpu,
        "ram": ram,
        "storage": storage,
        "gpu": gpu,
        "amount": amount,
        "quantity": quantity,
        "tx_start_ts": tx_start_ts,
        "seller_energy": seller_energy,
        "resource_type": resource_type,
        "score": score,
        "lease_duration": lease_duration,
        "price": price
    }
    try:
        msg = json.dumps(tx)
        rd.publish(channel, msg)
        logger.info(f"Message has been published to Redis: {msg}")
    except Exception as e:
        logger.error(f"Received error while publishing to redis: {e}")
