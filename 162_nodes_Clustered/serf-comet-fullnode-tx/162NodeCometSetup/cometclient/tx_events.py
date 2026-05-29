import asyncio
import json
import logging
import websockets
import sellers_discovery
#import push_to_redis

MAX_SEEN = 500

COMETBFT_WS_URL = "ws://localhost:26657/websocket"
logger = logging.getLogger(__name__)


def parse_event_attributes(event: dict) -> dict:
    """Decode key-value attributes from a CometBFT event."""
    decoded = {}
    for attr in event.get("attributes", []):
        try:
            decoded[attr["key"]] = attr["value"]
        except Exception as e:
            logger.error(f"Failed to decode attribute: {e}")
    return decoded


def handle_failed_tx(decoded_attrs: dict, seen_tx_hashes: set) -> bool:
    """
    Process a failedTx event. Returns True if successfully handled,
    False if duplicate or invalid.
    """
    status = decoded_attrs.get("status")
    if status != "Failed":
        return False

    tx_json = decoded_attrs.get("tx")
    if not tx_json:
        logger.warning("Missing tx payload in failedTx event")
        return False

    try:
        tx_details = json.loads(tx_json)
    except Exception as e:
        logger.error(f"Failed to parse failedTx JSON: {e}")
        return False

    tx_hash = tx_details.get("tx_hash")
    if tx_hash:
        if tx_hash in seen_tx_hashes:
            logger.info(f"Duplicate failedTx ignored: {tx_hash}")
            return False
        seen_tx_hashes.add(tx_hash)
        if len(seen_tx_hashes) > MAX_SEEN:
            seen_tx_hashes.clear()

    logger.info("🚨 Failed Tx Detected:")
    logger.info(json.dumps(tx_details, indent=2))
    logger.info("Sending the failed tx to buyer.")
    sellers_discovery.notify_fail_tx_buyer(tx_details)
    return True


# def handle_ongoing_tx(decoded_attrs: dict, seen_tx_hashes: set) -> bool:
#     """
#     Process an ongoingTx event. Returns True if successfully handled,
#     False if duplicate or invalid.
#     """
#     status = decoded_attrs.get("status")
#     if status != "OnGoing":
#         return False
#
#     tx_json = decoded_attrs.get("tx")
#     if not tx_json:
#         logger.warning("Missing tx payload in ongoingTx event")
#         return False
#
#     try:
#         tx_details = json.loads(tx_json)
#     except Exception as e:
#         logger.error(f"Failed to parse ongoingTx JSON: {e}")
#         return False
#
#     tx_hash = tx_details.get("tx_hash")
#     if tx_hash:
#         if tx_hash in seen_tx_hashes:
#             logger.info(f"Duplicate ongoingTx ignored: {tx_hash}")
#             return False
#         seen_tx_hashes.add(tx_hash)
#         if len(seen_tx_hashes) > MAX_SEEN:
#             seen_tx_hashes.clear()
#
#     logger.info("⏳ Ongoing Tx Detected:")
#     logger.info(json.dumps(tx_details, indent=2))
#     logger.info("Sending the ongoing tx to Emulate.")
#     push_to_redis.publish_to_emulate(tx_details)
#     return True


# Map event type strings to their handler functions
EVENT_HANDLERS = {
    "failedTx": handle_failed_tx,
#    "ongoingTx": handle_ongoing_tx,
}


async def subscribe():
    seen_tx_hashes = set()
    while True:
        try:
            async with websockets.connect(COMETBFT_WS_URL) as websocket:
                subscribe_msg = {
                    "jsonrpc": "2.0",
                    "method": "subscribe",
                    "id": "1",
                    "params": {
                        "query": "tm.event='Tx'"
                    }
                }

                await websocket.send(json.dumps(subscribe_msg))
                logger.info("Subscribed to Tx events")

                while True:
                    response = await websocket.recv()
                    data = json.loads(response)
#                    logger.info("Raw event:\n%s", json.dumps(data, indent=2))

                    result = data.get("result")
                    if not result:
                        continue

                    event_data = result.get("data")
                    if not event_data:
                        continue

                    value = event_data.get("value")
                    if not value:
                        continue

                    tx_result = value.get("TxResult")
                    if not tx_result:
                        continue

                    events = tx_result.get("result", {}).get("events", [])
                    if not events:
                        continue

                    for event in events:
                        event_type = event.get("type")
                        handler = EVENT_HANDLERS.get(event_type)
                        if handler is None:
                            logger.debug(f"Unhandled event type: {event_type}")
                            continue

                        decoded_attrs = parse_event_attributes(event)
                        handler(decoded_attrs, seen_tx_hashes)

        except Exception as e:
            logger.error(f"WebSocket error: {e}. Reconnecting in 2s...")
            await asyncio.sleep(2)