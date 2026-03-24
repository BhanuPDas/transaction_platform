import json
import logging
import requests

SERF_URL = "http://127.0.0.1:5555"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def create_pricing_payload(buyer, seller, quantity, score_ram, price, tx_id, tx_committed_time):
    """
    Creates the JSON payload for our transaction.
    """
    tx = {
        "seller_energy": 0.0,
        "buyer": buyer,
        "seller": seller,
        "price": price,
        "quantity": quantity,
        "seller_score": score_ram,
        "resource_type": "RAM",
        "transaction id": tx_id,
        "time": tx_committed_time
    }
    logger.info(f"Prepared transaction: {json.dumps(tx)}")
    return tx

def send_p2p_event(tx):
    logger.info(f"Triggering P2P user events {SERF_URL}/trigger_event")
    response = requests.get(f"{SERF_URL}/trigger_event", timeout=5)
    #if response.status_code == 200:

