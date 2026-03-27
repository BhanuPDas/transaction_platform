import requests
import json
import datetime
import logging
import transactions
import trigger_liqo
from flask import Flask, request, jsonify

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
        if not data or not data.get("buyer") or not data.get("seller") or not data.get("seller_ip") or not data.get(
                "buyer_ip"):
            logger.info(f"Invalid request received: {data}")
            return jsonify({"error": "Invalid request received"}), 400
        buyer_name = data.get("buyer")
        seller = data.get("seller")
        buyer_ip_addr = data.get("buyer_ip")
        seller_ip = data.get("seller_ip")
        cpu = data.get("cpu")
        ram = data.get("ram")
        storage = data.get("storage")
        gpu = data.get("gpu")
        resource_type = data.get("resource_type")
        amount = data.get("amount")
        score = data.get("score")
        quantity = data.get("quantity")
        price = data.get("price")
        lease_duration = data.get("lease_duration")
        tx_start_ts = datetime.datetime.now().isoformat()
        seller_energy = 0.0
        logger.info(f"Received transaction request between BUYER: {buyer_name} and SELLER: {seller}")
        transactions.check_comet_status()
        logger.info(f"Preparing payload for transaction..")
        tx_payload = transactions.create_tx_payload(buyer_name, seller, amount, quantity, score, price, resource_type,
                                                    tx_start_ts, lease_duration, seller_energy)
        tx_hash = transactions.broadcast_transaction(tx_payload)
        logger.info(f"Broadcast Hash received from cometbft: {tx_hash}")
        if tx_hash:
            trigger_liqo.publish_redis(buyer_name, buyer_ip_addr, seller, seller_ip, cpu, ram, storage, gpu, amount, score,
                                       quantity, price, lease_duration, tx_start_ts, seller_energy, resource_type)
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
