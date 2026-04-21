import json
import websockets
import logging

COMETBFT_WS_URL = "ws://localhost:26657/websocket"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


async def subscribe():
    async with websockets.connect(COMETBFT_WS_URL) as websocket:
        subscribe_msg = {
            "jsonrpc": "2.0",
            "method": "subscribe",
            "id": "1",
            "params": {
                "query": "tm.event='Tx' AND failedTx.status='FAILED'"
            }
        }

        await websocket.send(json.dumps(subscribe_msg))
        logger.info("Subscribed to tx failure events")

        while True:
            response = await websocket.recv()
            data = json.loads(response)
            logger.info("Received event:\n", json.dumps(data, indent=2))
            
