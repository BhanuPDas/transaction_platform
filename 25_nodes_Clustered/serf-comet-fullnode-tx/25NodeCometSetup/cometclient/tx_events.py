import asyncio
import json
import logging
import websockets
import sellers_discovery

MAX_SEEN = 10_000

COMETBFT_WS_URL = "ws://localhost:26657/websocket"
logger = logging.getLogger(__name__)


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
                logger.info("Subscribed to tx failure events")

                while True:
                    response = await websocket.recv()
                    data = json.loads(response)

                    logger.info("Raw event:\n%s", json.dumps(data, indent=2))

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
                        if event.get("type") != "failedTx":
                            continue

                        decoded_attrs = {}

                        for attr in event.get("attributes", []):
                            try:
                                key = attr["key"]
                                val = attr["value"]
                                decoded_attrs[key] = val
                            except Exception as e:
                                logger.warning(f"Failed to decode attribute: {e}")
                                continue

                        status = decoded_attrs.get("status")
                        if status != "Failed":
                            continue

                        tx_json = decoded_attrs.get("tx")
                        if not tx_json:
                            logger.warning("Missing tx payload in event")
                            continue

                        try:
                            tx_details = json.loads(tx_json)
                            tx_hash = tx_details.get("tx_hash")
                            if tx_hash:
                                if tx_hash in seen_tx_hashes:
                                    logger.info(f"Duplicate event ignored: {tx_hash}")
                                    continue
                                seen_tx_hashes.add(tx_hash)
                                if len(seen_tx_hashes) > MAX_SEEN:
                                    seen_tx_hashes.clear()
                        except Exception as e:
                            logger.error(f"Failed to parse tx JSON: {e}")
                            continue

                        logger.info("🚨 Failed Tx Detected:")
                        logger.info(json.dumps(tx_details, indent=2))
                        logger.info("Sending the failed tx to buyer.")
                        sellers_discovery.notify_fail_tx_buyer(tx_details)

        except Exception as e:
            logger.error(f"WebSocket error: {e}. Reconnecting in 2s...")
            await asyncio.sleep(2)