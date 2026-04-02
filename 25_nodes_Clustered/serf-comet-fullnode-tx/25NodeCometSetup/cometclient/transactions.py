import requests
import json
import logging
# import sys
import urllib.parse
import base64

# URL for your CometBFT node's RPC
COMETBFT_RPC_URL = "http://127.0.0.1:26657"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class CometNotReadyError(Exception):
    pass


def create_tx_payload(buyer, seller, amount, tx_start_ts, lease_duration):
    tx = {
        "type": "transfer",
        "buyer": buyer,
        "seller": seller,
        "amount": amount,
        "tx_start_ts": tx_start_ts,
        "lease_duration": lease_duration,
        "seller_energy": 0.0
    }
    logger.info(f"Prepared transaction: {json.dumps(tx)}")
    return tx


def check_comet_status():
    logger.info(f"Checking Cometbft Health {COMETBFT_RPC_URL}/health.....")
    try:
        response = requests.get(f"{COMETBFT_RPC_URL}/health", timeout=5)
        response.raise_for_status()
        data = response.json()

        if "result" in data and isinstance(data["result"], dict) and not data["result"]:
            logger.info("CometBFT node is healthy")
        elif "error" in data:
            logger.error(f"CometBFT error: {data['error']}")
        else:
            logger.error(f"Unexpected response format: {data}")

    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")

    logger.info(f"Checking Cometbft current status {COMETBFT_RPC_URL}/status....")
    try:
        response = requests.get(f"{COMETBFT_RPC_URL}/status", timeout=5)
        response.raise_for_status()
        data = response.json()

        sync_info = data.get("result", {}).get("sync_info", {})
        catching_up = sync_info.get("catching_up")

        if catching_up is True:
            logger.error("⚠️  CometBFT node is still syncing blocks. Try after sometime. Terminating execution...")
            raise CometNotReadyError("CometBFT node is still syncing blocks.")
            # sys.exit(1)
        elif catching_up is False:
            logger.info("✅  CometBFT node is fully synchronized and ready for transactions.")
        else:
            logger.error("❌  Unable to determine catching_up status. Invalid or missing field.")

    except Exception as e:
        logger.error(f"❌  Request failed: {e}")
        raise CometNotReadyError("Request failed")
        # sys.exit(1)
    return None


def dial_peers(peers: list[str], persistent: bool = False):
    """
    Dials a list of peers using /dial_peers.
    Each peer string should be in format: <node_id>@<ip>:<port>
    """
    try:
        peers_json = json.dumps(peers)
        params = {
            "peers": peers_json,
            "persistent": str(persistent).lower()
        }
        url = f"{COMETBFT_RPC_URL}/dial_peers?" + urllib.parse.urlencode(params)
        logger.info(f"[P2P] Dialing peers: {peers}")
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        logger.info(f"[P2P] Dial response: {data}")
    except requests.RequestException as e:
        logger.error(f"[P2P] Failed to dial peers: {e}")
    return None


def broadcast_transaction(tx_json):
    """
    Encodes and broadcasts the transaction to the CometBFT node via JSON-RPC.
    """
    try:
        # Step 1: Convert the JSON transaction to bytes, then Base64 encode it
        tx_bytes = json.dumps(tx_json).encode('utf-8')
        tx_base64 = base64.b64encode(tx_bytes).decode('utf-8')
        logger.info(f"Base64 encoded: {tx_base64}")

        # Step 2: Prepare the JSON-RPC payload
        params = {"tx": f'"{tx_base64}"'}

        # Step 3: Send the request to the CometBFT node
        logger.info(f"Broadcasting tx to {COMETBFT_RPC_URL} via JSON-RPC...")
        url = f"{COMETBFT_RPC_URL}/broadcast_tx_sync"
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()  # Raise an exception for bad HTTP status (4xx or 5xx)

        response_json = response.json()
        if "error" in response_json:
            logger.error("Transaction broadcast FAILED (RPC error)")
            logger.error(response_json["error"])
            return ""

        if "result" in response_json:
            result = response_json["result"]
            broadcast_tx_hash = response_json.get("result", {}).get("hash", "")
            if result.get("code") == 0:
                logger.info("\nTransaction Accepted!")
                logger.info(f"CometBFT Response: {result}")
                return broadcast_tx_hash
            else:
                logger.info("\nTransaction was REJECTED by CheckTx.")
                logger.info(f"CometBFT Response: {result}")

    except Exception as e:
        logger.error(f"\nTransaction broadcast FAILED. An error occurred:")
        logger.error(f"Error: {e}")

    return ""


def search_tx(tx_hash: str):
    logger.info(f"Validation url:  {COMETBFT_RPC_URL}/tx  Transaction hash: {tx_hash}")
    try:
        url = f"{COMETBFT_RPC_URL}/tx"
        params = {"hash": f"0x{tx_hash.lstrip('0x')}", "prove": "true"}
        logger.info(f"Request url: {url} Params: {params}")
        response = requests.get(url, params=params, timeout=3)
        res = response.json()
        if "error" in res:
            logger.error(f"Error received while validating transaction: {res}")
        else:
            result = res.get("result", {})
            if result:
                tx_height = result.get("height", "")
                return tx_height
            else:
                logger.error(f"Transaction {tx_hash} not found...")
    except Exception as ex:
        logger.error(f"Exception raised {ex}")
    return ""


def get_tx_block(block_height):
    logger.info(f"Url:  {COMETBFT_RPC_URL}/block  Height: {block_height}")
    try:
        url = f"{COMETBFT_RPC_URL}/block"
        params = {"height": block_height}
        response = requests.get(url, params=params, timeout=3)
        response.raise_for_status()
        res = response.json()
        if "error" in res:
            logger.error(f"Error received while fetching tx block: {res}")
        else:
            result = res.get("result", {})
            block_id = result.get("block_id", {})
            tx_id = block_id.get("hash")
            header = result.get("block", {}).get("header", {})
            tx_committed_time = header.get("time")
            return tx_id, tx_committed_time
    except Exception as ex:
        logger.error(f"Exception raised {ex}")
    return "", ""
