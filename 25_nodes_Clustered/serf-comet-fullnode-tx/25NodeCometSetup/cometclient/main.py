import random
import requests
import json
import time
import datetime
import logging
import transactions
import pricing
import trigger_liqo
import math

# --- Configuration ---
# URL for your colleague's Hilbert service
HILBERT_URL = "http://127.0.0.1:4041/hilbert-output"
SERF_URL = "http://127.0.0.1:5555"
BUYER_NODE_JSON = "/opt/serfapp/node.json"

# How often to poll for new data
POLL_INTERVAL_SECONDS = 60

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


# --- End Configuration ---

def find_best_seller(api_data):
    """
    Parses the Hilbert API data and finds the seller with the lowest price_per_ram.
    """
    try:
        results = api_data.get("results", [])
        best_seller = None
        lowest_price = float('inf')
        seller_ip = None
        cpu = 0
        ram = 0.0
        storage = 0
        gpu = 0
        score_ram = 0.0

        logger.info("--- Scanning for Sellers ---")
        for node in results:
            node_name = node.get("name")
            price = node.get("price_per_ram")

            if node_name and price is not None:
                logger.info(f"  - Considering node '{node_name}' (Price: {price})")
                if price < lowest_price:
                    lowest_price = price
                    best_seller = node_name
                    seller_ip = node.get("ip", None)
                    cpu = node.get("cpu", 0)
                    ram = node.get("ram", 0.0)
                    storage = node.get("storage", 0)
                    gpu = node.get("gpu", 0)
                    score_ram = node.get("score_per_ram", 0.0)

        if best_seller:
            logger.info(f"--- Found best seller: '{best_seller}' at price {lowest_price} ---")
            # Take arbitary data for quantity and amount
            quantity = random.randint(1, round(ram)-1)
            amount = math.ceil(quantity * lowest_price)
            return best_seller, amount, seller_ip, cpu, ram, storage, gpu, quantity, score_ram, lowest_price
        else:
            logger.info("--- No valid sellers found. ---")
            return None, 0, None, 0, 0.0, 0, 0, 0, 0.0, 0.0

    except Exception as e:
        logger.error(f"Error parsing Hilbert data: {e}")
        return None, 0


def get_node_name(json_path):
    try:
        with open(json_path, 'r') as file:
            data = json.load(file)
            node_name = data.get("node_name")
            if node_name is None:
                raise KeyError("Key 'node_name' not found in JSON file.")
            return node_name
    except FileNotFoundError:
        logger.error(f"Error: File not found at {json_path}")
    except json.JSONDecodeError:
        logger.error(f"Error: Invalid JSON format in {json_path}")
    except Exception as e:
        logger.error(f"Error: {e}")


def get_nodeip_and_bftaddr(buyer: str):
    logger.info(f"Checking Active members from {SERF_URL}/members")
    buyer_ip = None
    response = requests.get(f"{SERF_URL}/members", timeout=5)
    if response.status_code == 200:
        members_data = response.json()
        bft_peers = []
        for member in members_data:
            if member.get("Name") == buyer:
                buyer_ip = member.get("Addr", None)
            tags = member.get("Tags", {})
            bft_addr = tags.get("rpc_addr")
            if bft_addr:
                bft_peers.append(bft_addr)
        return bft_peers, buyer_ip
    else:
        logger.error("Failed to get members from Serf.")
        return [], None


def main_loop():
    buyer = get_node_name(BUYER_NODE_JSON)
    # Important: Dial Peers to connect Peers
    bft_addr, buyer_ip = get_nodeip_and_bftaddr(buyer)
    transactions.dial_peers(peers=bft_addr, persistent=True)
    # Check Comet health and current status
    transactions.check_comet_status()
    logger.info("--- Hilbert Core Client ---")
    logger.info(f"Polling {HILBERT_URL} every {POLL_INTERVAL_SECONDS} seconds.")
    logger.info(f"Buyer node is: {buyer}")
    logger.info("---------------------------")
    tx_hash = ""
    seller = None
    seller_ip = None
    cpu = 0
    ram = 0.0
    storage = 0
    gpu = 0
    amount = 0
    quantity = 0
    score_ram = 0.0
    lowest_price = 0.0

    while True:
        try:
            logger.info(f"\n[{datetime.datetime.now().isoformat()}] Polling Hilbert for data...")
            # Fetch data from Hilbert
            response = requests.get(HILBERT_URL, timeout=5)
            response.raise_for_status()
            api_data = response.json()

            # Find the best seller
            seller, amount, seller_ip, cpu, ram, storage, gpu, quantity, score_ram, lowest_price = find_best_seller(
                api_data)

            if seller and amount > 0:
                # Create and broadcast the transaction
                tx_payload = transactions.create_tx_payload(buyer, seller, amount, quantity, score_ram, lowest_price)
                tx_hash = transactions.broadcast_transaction(tx_payload)

        except Exception as e:
            logger.error(f"An unexpected error occurred in main loop: {e}")

        time.sleep(10)
        logger.info("Fetching Transaction Block...")
        block_height = transactions.search_tx(tx_hash)
        if block_height > 0:
            tx_id, tx_committed_time = transactions.get_tx_block(block_height)
            if tx_id and tx_committed_time:
                logger.info(f"Transaction has been committed. Tx ID: {tx_id} Date: {tx_committed_time}")
                pr_tx = pricing.create_pricing_payload(buyer, seller, quantity, score_ram, lowest_price, tx_id, tx_committed_time)
                pricing.send_p2p_event(pr_tx)
                trigger_liqo.publish_redis(buyer, buyer_ip, seller, seller_ip, cpu, ram, storage, gpu, amount, quantity)
            else:
                logger.error("Transaction record not found.")
        else:
            logger.info("Transaction Block not found.")
        logger.info(f"\nWaiting {POLL_INTERVAL_SECONDS} seconds before next poll...")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main_loop()
