import requests
import json
from datetime import datetime, timezone
import logging
import transactions
import trigger_liqo
from flask import Flask, request, jsonify
import sellers_discovery

# --- Configuration ---
SERF_URL = "http://127.0.0.1:5555"
BUYER_NODE_JSON = "/opt/serfapp/node.json"
app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


# --- End Configuration ---

class CometNotReadyError(Exception):
    pass


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


def get_nodeip_and_bftaddr(buyer_node: str):
    logger.info(f"Checking Active members from {SERF_URL}/members")
    buyer_node_ip = None
    response = requests.get(f"{SERF_URL}/members", timeout=5)
    if response.status_code == 200:
        members_data = response.json()
        bft_peers = []
        for member in members_data:
            if member.get("Name") == buyer_node:
                buyer_node_ip = member.get("Addr", None)
            tags = member.get("Tags", {})
            bft_addr = tags.get("rpc_addr")
            if bft_addr:
                bft_peers.append(bft_addr)
        return bft_peers, buyer_node_ip
    else:
        logger.error("Failed to get members from Serf.")
        return [], None


@app.route('/initiate_tx', methods=['POST'])
def get_transaction():
    try:
        data = request.get_json(silent=True)
        logger.info(f"Received request: {data}")
        if not data:
            logger.info("Empty or malformed JSON received")
            return jsonify({"error": "Invalid request received"}), 400
        ip = data.get("ip")
        lease_duration = data.get("lease_duration")
        resources = data.get("resources")

        if not ip or not lease_duration or not resources:
            logger.info(f"Missing required fields in request: {data}")
            return jsonify({"error": "Invalid request received"}), 400

        # Optional: validate that at least one resource has non-zero demand
        active_resources = {
            k: v for k, v in resources.items()
            if v.get("demand_per_unit", 0) > 0
        }
        if not active_resources:
            logger.info(f"No active resource demands in request: {data}")
            return jsonify({"error": "At least one resource must have demand_per_unit > 0"}), 400

        #Buyers demand will be done by scripts
        #sellers_discovery.notify_buyer(ip=ip, resources=resources)
        discovered = sellers_discovery.find_sellers()
        tx_start_ts = datetime.now(timezone.utc).isoformat()
        empty_seller = sellers_discovery.create_empty_sellers()
        if not discovered:
            logger.info("No sellers discovered, proceeding with empty seller")
            seller_obj = empty_seller
            amount = 0
        else:
            api_data = discovered.get("results")
            seller_rec = sellers_discovery.select_seller(resources, api_data)
            if not seller_rec:
                logger.info("No suitable seller found, using empty seller")
                seller_obj = empty_seller
                amount = 0
            else:
                amount = seller_rec.get("amount")
                raw_seller = seller_rec.get("seller")
                seller_obj = sellers_discovery.create_seller(raw_seller)
            logger.info(f"Selected seller: {seller_rec}")
            logger.info(f"Received transaction request — BUYER: {buyer}, SELLER: {seller_obj['name'] or 'none'}")
            transactions.check_comet_status()
            logger.info("Preparing payload for transaction...")
        buyer_obj = {
            "name": buyer,
            "ip": ip,
            "resource": resources
        }

        tx_payload = transactions.create_tx_payload(buyer=buyer_obj,
                                                    seller=seller_obj,
                                                    amount=amount,
                                                    tx_start_ts=tx_start_ts,
                                                    lease_duration=lease_duration
                                                    )

        tx_hash = transactions.broadcast_transaction(tx_payload)
        if tx_hash:
            trigger_liqo.publish_redis(buyer_obj, seller_obj, amount, tx_start_ts, lease_duration)
            return jsonify({"status": "success", "message": f"Resource Trade initiated: {tx_hash}"}), 200
        else:
            return jsonify({"status": "error", "message": "Error Occured in Transaction. Try Again"}), 400

    except CometNotReadyError as e:
        logger.error(str(e))
    except Exception as exc:
        logger.error(f"Unexpected error: {exc}")

if __name__ == "__main__":
    try:
        buyer = get_node_name(BUYER_NODE_JSON)
        # Important: Dial Peers to connect Peers
        bftaddr, bip = get_nodeip_and_bftaddr(buyer)
        buyer_ip = bip
        transactions.dial_peers(peers=bftaddr, persistent=True)
        app.run(debug=True, host='0.0.0.0', port=5665)
    except Exception as ex:
        logger.error(f"Unexpected error: {ex}")
