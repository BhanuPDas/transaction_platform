from flask import Flask, request, jsonify
import logging
import requests
import time
import base64
import json

COMETBFT_RPC_URL = "http://127.0.0.1:26657"

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
app = Flask(__name__)


class CometNotReadyError(Exception):
    pass

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
            logger.error("⚠️  CometBFT node is still syncing blocks. Try after sometime....")
            raise CometNotReadyError("CometBFT node is still syncing blocks. Try after sometime")
        elif catching_up is False:
            logger.info("✅  CometBFT node is fully synchronized and ready for transactions.")

    except requests.exceptions.RequestException as e:
        logger.error(f"❌  Request failed: {e}")
        raise CometNotReadyError("Request failed")
    return None

def broadcast_transaction(tx_json):
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
        broadcast_tx_hash = response_json.get("result", {}).get("hash")

        if "result" in response_json:
            result = response_json["result"]
            if result.get("code") == 0:
                logger.info("\nTransaction broadcast successful!")
                logger.info(f"CometBFT Response: {result}")
            else:
                logger.info("\nTransaction was REJECTED by CheckTx.")
                logger.info(f"CometBFT Response: {result}")
        else:
            logger.info(f"\nTransaction broadcast FAILED. Unexpected response:")
            logger.info(response_json)

        return broadcast_tx_hash

    except requests.exceptions.ConnectionError as e:
        logger.error(f"\nTransaction broadcast FAILED. Could not connect to CometBFT RPC.")
        logger.error(f"Error: {e}")
        return None
    except Exception as e:
        logger.error(f"\nTransaction broadcast FAILED. An error occurred:")
        logger.error(f"Error: {e}")
        return None


def validate_transaction(tx_hash: str):
    logger.info(f"Validation url:  {COMETBFT_RPC_URL}/tx  Transaction hash: {tx_hash}")
    try:
        url = f"{COMETBFT_RPC_URL}/tx"
        params = {"hash": f"0x{tx_hash.lstrip('0x')}", "prove": "true"}
        response = requests.get(url, params=params, timeout=3)
        result = response.json()
        error = result.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            if isinstance(code, int) and code < 0:
                logger.error(f"Error while validating tx: {error}")
                return f"Error while validating transaction: {error}"

        tx_result = result.get("result")
        if tx_result:
            logger.info(f"Transaction Results for {tx_hash}: {tx_result}")
            return tx_result
        else:
            logger.error(f"Transaction {tx_hash} not found...")
            return f"Transaction Error: {tx_hash} not found..."
    except requests.exceptions.RequestException as e:
        logger.error(f"❌  Request failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Exception raised {e}")
        return None


@app.route('/validatorTx', methods=['POST'])
def update_validator():
    try:
        tx_payload = request.get_json(silent=True)
        if not tx_payload or not tx_payload.get("type") or not tx_payload.get("validator"):
            logger.info(f"Invalid request received: {tx_payload}")
            return jsonify({"error": "Invalid request received"}), 400
        logger.info(f"Received transaction request to update CometBFT validators: {tx_payload}")
        check_comet_status()
        logger.info(f"Preparing payload for transaction..")
        tx_hash = broadcast_transaction(tx_payload)
        logger.info(f"Broadcast Hash received from cometbft: {tx_hash}")
        if tx_hash:
            logger.info("Validating broadcast status from cometbft in 2 sec...")
            time.sleep(2)
            tx_result = validate_transaction(tx_hash)
            if tx_result:
                return jsonify({"status": "success", "message": tx_result}), 200
            else:
                return jsonify({"status": "error", "message": tx_result}), 400
        else:
            return jsonify({"status": "error", "message": "Error occurred during transaction broadcast"}), 400
    except CometNotReadyError as e:
        logger.error(str(e))
        return jsonify({"status": "error", "message": str(e)}), 503
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500


if __name__ == '__main__':
    try:
        app.run(debug=True, host='0.0.0.0', port=5010)
    except Exception as ex:
        logger.error(f"Unexpected error: {ex}")