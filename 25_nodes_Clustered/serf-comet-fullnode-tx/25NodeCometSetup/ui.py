import streamlit as st
import requests
import json
import time
import base64
import datetime
import logging
import pandas as pd
import altair as alt
import re


POLL_INTERVAL_SECONDS = 120

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


buyer_nodes_map = {
        "serf1":"clab-century-serf1", "serf2":"clab-century-serf2",
        "serf3":"clab-century-serf3","serf4":"clab-century-serf4",
        "serf5":"clab-century-serf5","serf6":"clab-century-serf6",
        "serf7":"clab-century-serf7","serf8":"clab-century-serf8"
        }

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

        if best_seller:
            logger.info(f"--- Found best seller: '{best_seller}' at price {lowest_price} ---")
            # Convert float price (e.g., 1.79) to integer tokens (e.g., 179)
            amount_in_tokens = int(lowest_price * 100)
            return best_seller, amount_in_tokens, seller_ip, cpu, ram, storage, gpu
        else:
            logger.info("--- No valid sellers found. ---")
            return None, 0, None, 0, 0.0, 0, 0



    except Exception as e:
        logger.error(f"Error parsing Hilbert data: {e}")
        return None, 0


def create_transaction(buyer, seller_name, amount):
    """
    Creates the JSON payload for our transaction.
    """
    tx = {
        "type": "transfer",
        "from_node": buyer,
        "to_node": seller_name,
        "amount": f"{amount} tokens",
        "timestamp": datetime.datetime.now().isoformat()
    }
    logger.info(f"Prepared transaction: {json.dumps(tx)}")
    return tx


def broadcast_transaction(tx_json, sbuyer):
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
        logger.info(f"Broadcasting tx to {sbuyer} via JSON-RPC...")
        url = f"http://{sbuyer}:26657/broadcast_tx_sync"
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
    except Exception as e:
        logger.error(f"\nTransaction broadcast FAILED. An error occurred:")
        logger.error(f"Error: {e}")


if __name__ == "__main__":
    st.set_page_config(
        page_title="Trade Resources",
        layout="wide",
        page_icon="icon.jpg",
    )
    with open("bgImage.png", "rb") as f:
        img_data = base64.b64encode(f.read()).decode()
    st.markdown(
        f"""
            <style>
            [data-testid="stAppViewContainer"] {{
                background-image: url("data:image/png;base64,{img_data}");
                background-size: cover;
                background-position: center;
                background-repeat: no-repeat;
            }}
            /* Import modern font */
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
            html, body, [class*="css"] {{
                font-family: 'Inter', sans-serif;
            }}
            /* Glass container effect */
            .glass {{
                background: rgba(255, 255, 255, 0.12);
                backdrop-filter: blur(12px);
                -webkit-backdrop-filter: blur(12px);
                border-radius: 16px;
                padding: 24px;
                border: 1px solid rgba(255,255,255,0.25);
                box-shadow: 0 8px 32px rgba(0,0,0,0.25);
            }}
            /* Titles */
            .glass h1,.glass h2,.glass h3 {{
                color: #171716 !important;
                font-weight: 700;
            }}
            .glass p {{
                color: ##171716;
            }}
            /* Text */
            [data-testid="stVerticalBlock"] [data-testid="stWidgetLabel"] p {{
                color: #171716 !important;
                font-size: 15px;
                font-weight: 600;
                letter-spacing: 0.03em;
                text-transform: uppercase;
            }}
            
            /* Buttons */
            .stButton>button {{
                background: linear-gradient(135deg, #00f5a0, #00d9f5);
                color: black;
                border-radius: 10px;
                padding: 0.6rem 1.2rem;
                border: none;
                font-weight: 600;
                transition: all 0.2s ease-in-out;
            }}
            .stButton>button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(0,0,0,0.35);
            }}
            /* Selectbox / Inputs */
            .stSelectbox, .stNumberInput {{
                background: rgba(255,255,255,0.15);
                border-radius: 10px;
            }}
            /* Charts */
            [data-testid="stVegaLiteChart"] {{
                background: rgba(255,255,255,0.1) !important;
                border-radius: 12px;
                padding: 0px;
                box-sizing: border-box;
            }}
            [data-testid="stVegaLiteChart"] > div {{
                border-radius: 12px;
                overflow: hidden;
            }}
            </style>
            """,
        unsafe_allow_html=True
    )

    st.markdown(
    """
    <div class="glass">
        <h1>🏪 Trade Resources</h1>
        <p>
        Buy & Sell compute resources across the network in real-time.
        </p>
    </div>
    """,
    unsafe_allow_html=True
)
    st.write("")
    cols = st.columns([1, 2])
    buyers = [k for k in buyer_nodes_map.keys()]
    left_cell = cols[0].container(
        border=True, height="stretch", vertical_alignment="center"
    )
    selected_buyer = None
    with left_cell:
        st.markdown(
            """
            <div class="glass">
                <h3>🧾 Order Resources</h3>
            </div>
            """,
            unsafe_allow_html=True
        )
        ""  # Add space
        try:
            buyer = st.selectbox("Select Buyer", buyers, index=None, placeholder="Select Buyer")
            seller = None
            if buyer:
                selected_buyer = buyer_nodes_map.get(buyer)
                response = requests.get(f"http://{selected_buyer}:4041/hilbert-output", timeout=5)
                response.raise_for_status()
                api_data = response.json()
                seller_node, amt_seller, seller_ip, cpu, ram, storage, gpu = find_best_seller(api_data)
                seller = st.selectbox("Matched Seller", seller_node, disabled=True)
                st.number_input("CPU Demand", value=cpu, disabled=True)
                st.number_input("RAM Demand", value=ram, disabled=True)
                st.number_input("Storage Demand", value=storage, disabled=True)
                st.number_input("GPU Demand", value=gpu, disabled=True)
                amount = st.number_input("Payment Due Per Unit Time", value=amt_seller, disabled=True)
                if st.button("Execute Order"):
                    if seller and amount > 0:
                        tx_payload = create_transaction(buyer, seller, amount)
                        with st.spinner("Broadcasting transaction…..."):
                            tx_hash = broadcast_transaction(tx_payload,selected_buyer)
                            time.sleep(2)
                        st.success("Transaction Broadcasted successfully!")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Error connecting to Hilbert URL http://{selected_buyer}:4041/hilbert-output: {e}")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error from Hilbert URL: {e}")
        except json.JSONDecodeError:
            logger.error("Error: Could not decode JSON response from Hilbert.")
        except Exception as e:
            logger.error(f"An unexpected error occurred in code: {e}")


    right_cell = cols[1].container(
        border=True, height="stretch", vertical_alignment="center"
    )
    with right_cell:
        st.markdown(
            """
            <div class="glass">
                <h2>💰 Network Balances</h2>
            </div>
            """,
            unsafe_allow_html=True
        )
        ""#Add space
        chart_placeholder = st.empty()
        @st.fragment(run_every="20s")
        def update_ledger_chart():
            try:
                if not buyer and not seller:
                    selected_buyers_default = buyer_nodes_map.get("serf1")
                    ledger_response = requests.get(f"http://{selected_buyers_default}:26657/abci_query?data=%22balance%22", timeout=5)
                else:
                    ledger_response = requests.get(f"http://{selected_buyer}:26657/abci_query?data=%22balance%22", timeout=5)
                ledger_response.raise_for_status()
                q_data = ledger_response.json()
                encoded_value = q_data.get("result", {}).get("response", {}).get("value")
                if encoded_value:
                    decoded_json = json.loads(base64.b64decode(encoded_value).decode('utf-8'))
                    sorted_items = sorted(decoded_json.items(), key=lambda x: int(re.search(r'\d+', x[0]).group()))
                    df = pd.DataFrame(sorted_items, columns=["Node","Balance"])
                    HIGHLIGHT_COLOR = "#2813E8"
                    MUTED_COLOR = "#A8A6A5"
                    targets = [buyer, seller]
                    active_targets = [t for t in targets if t]
                    highlight_condition = alt.condition(
                        alt.FieldOneOfPredicate(field='Node', oneOf=active_targets),
                        alt.value(HIGHLIGHT_COLOR),
                        alt.value(MUTED_COLOR)
                    )
                    chart = (
                        alt.Chart(df)
                        .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
                        .encode(
                            alt.X("Node:N", title="Node", sort=df["Node"].tolist()),
                            alt.Y("Balance:Q", title="Balance"),
                            color=highlight_condition,
                            tooltip=["Node", "Balance"]
                        )
                        .configure_legend(orient="bottom")
                        .configure_view(strokeOpacity=0)
                    )
                    chart_placeholder.altair_chart(chart, width="stretch")
                    logger.info(f"Fetching Balance in Ledger: {sorted_items}")
                else:
                    logger.error("No value found in response")
            except Exception as e:
                logger.error(f"\nQuery FAILED. An error occurred:")
                logger.error(f"Error: {e}")

        update_ledger_chart()

