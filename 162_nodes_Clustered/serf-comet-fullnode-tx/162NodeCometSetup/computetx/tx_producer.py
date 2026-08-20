"""
Status semantics:
  - "OnGoing": a seller was selected AND the buyer's budget covers the
    seller's prices for every demanded resource. Produced to the cluster's
    Kafka topic keyed by f"{tx_uuid}-{seller_name}", and pushed to Redis.
  - "Failed": either no seller could be selected, or the buyer's budget is
    too low for one or more demanded resources. Produced to the cluster's
    Kafka topic on a round-robin partition. Not pushed to Redis (no trade
    actually happened).
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, request

import budget_check
import cluster_config
import logging_setup
import push_to_redis
import sellers_discovery
from kafka_producer import KafkaTxProducer

BUYER_NODE_JSON = os.environ.get("BUYER_NODE_JSON", "/opt/serfapp/node.json")
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

app = Flask(__name__)


def get_node_name(json_path: str) -> str:
    with open(json_path, "r") as file:
        data = json.load(file)
    node_name = data.get("node_name")
    if node_name is None:
        raise KeyError(f"Key 'node_name' not found in {json_path}")
    return node_name


def build_failed_payload(tx_uuid: str, buyer_obj: dict, log_message: str) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "status": "Failed",
        "tx_hash": tx_uuid,
        "tx_end_unix": int(now.timestamp()),
        "tx_end_ts": now.isoformat(),
        "tx": {
            "type": "transfer",
            "buyer": buyer_obj,
            "seller": sellers_discovery.create_empty_sellers(),
            "amount": 0,
            "tx_start_ts": now.isoformat(),
            "lease_duration": buyer_obj.get("lease_duration", 0),
        },
        "log": log_message,
    }


def build_ongoing_payload(tx_uuid: str, buyer_obj: dict, seller_obj: dict, amount: float,
                           tx_start_ts: str, lease_duration: int) -> dict:
    start_dt = datetime.fromisoformat(tx_start_ts)
    tx_end_unix = int(start_dt.timestamp()) + lease_duration * 60  # lease_duration is in minutes
    return {
        "status": "OnGoing",
        "tx_hash": tx_uuid,
        "tx_end_unix": tx_end_unix,
        "tx_end_ts": "",
        "tx": {
            "type": "transfer",
            "buyer": buyer_obj,
            "seller": seller_obj,
            "amount": amount,
            "tx_start_ts": tx_start_ts,
            "lease_duration": lease_duration,
        },
        "log": "Processing Transaction",
    }


@app.route("/scr_initiate_tx", methods=["POST"])
def get_transaction_scr():
    try:
        data = request.get_json(silent=True)
        logger.info(f"Received request: {data}")
        if not data or not data.get("Demand_output"):
            logger.info("Empty or malformed JSON received")
            return jsonify({"error": "Invalid request received"}), 400

        demand_output = data["Demand_output"]
        app_type = demand_output.get("app_type")
        ip = demand_output.get("ip")
        lease_duration = demand_output.get("lease_duration")
        resources = demand_output.get("resources")

        if not ip or not lease_duration or not resources:
            logger.info(f"Missing required fields in request: {data}")
            return jsonify({"error": "Invalid request received"}), 400

        active_resources = {
            k: v for k, v in resources.items() if v.get("demand_per_unit", 0) > 0
        }
        if not active_resources:
            logger.info(f"No active resource demands in request: {data}")
            return jsonify({"error": "At least one resource must have demand_per_unit > 0"}), 400

        tx_uuid = str(uuid.uuid4())
        tx_start_ts = datetime.now(timezone.utc).isoformat()
        buyer_obj = {"name": BUYER_NAME,"app_type": app_type, "ip": ip, "resource": resources}

        discovered = data.get("Hilbert_output", {})
        seller_rec = None
        if discovered:
            api_data = discovered.get("results")
            seller_rec = sellers_discovery.select_seller(resources, api_data, logger)

        # --- Failure case (a): no seller could be selected ---
        if not seller_rec:
            logger.info("No sellers discovered or no suitable seller found")
            payload = build_failed_payload(tx_uuid, buyer_obj, "No Seller Found For The Buyer Demand")
            producer.produce_failed(CLUSTER_ID, tx_uuid, payload)
            logger.info(f"Failed transaction {tx_uuid} produced to {cluster_config.get_topic(CLUSTER_ID)}")
            return jsonify({"status": "failed", "message": payload["log"], "tx_hash": tx_uuid}), 200

        amount = seller_rec.get("amount")
        raw_seller = seller_rec.get("seller")
        seller_obj = sellers_discovery.create_seller(raw_seller)
        logger.info(f"Selected seller: {seller_rec}")
        logger.info(f"Transaction candidate — BUYER: {BUYER_NAME}, SELLER: {seller_obj.get('name') or 'none'}")

        # --- Failure case (b): buyer's budget too low ---
        try:
            sufficient_budget = budget_check.has_high_budget(resources, seller_obj, logger)
        except budget_check.PricingMissingError as exc:
            logger.error(str(exc))
            payload = build_failed_payload(tx_uuid, buyer_obj, str(exc))
            producer.produce_failed(CLUSTER_ID, tx_uuid, payload)
            sellers_discovery.notify_fail_tx_buyer(payload, logger)
            return jsonify({"status": "failed", "message": payload["log"], "tx_hash": tx_uuid}), 200

        if not sufficient_budget:
            payload = build_failed_payload(tx_uuid, buyer_obj, "Buyer Has Very Low Budget For The Resources")
            producer.produce_failed(CLUSTER_ID, tx_uuid, payload)
            sellers_discovery.notify_fail_tx_buyer(payload, logger)
            logger.info(f"Failed transaction {tx_uuid} produced to {cluster_config.get_topic(CLUSTER_ID)}")
            return jsonify({"status": "failed", "message": payload["log"], "tx_hash": tx_uuid}), 200

        # --- Success: OnGoing ---
        payload = build_ongoing_payload(tx_uuid, buyer_obj, seller_obj, amount, tx_start_ts, lease_duration)
        producer.produce_ongoing(CLUSTER_ID, tx_uuid, seller_obj.get("name", ""), payload)
        logger.info(
            f"OnGoing transaction {tx_uuid} produced to {cluster_config.get_topic(CLUSTER_ID)} "
            f"keyed on seller={seller_obj.get('name')}"
        )

        push_to_redis.publish_to_liqo(payload, logger)

        return jsonify({"status": "success", "message": f"Resource trade initiated: {tx_uuid}"}), 200

    except Exception as exc:
        logger.error(f"Unexpected error: {exc}")
        return jsonify({"status": "error", "message": "Internal error processing transaction"}), 500



BUYER_NAME = get_node_name(BUYER_NODE_JSON)
logger = logging_setup.setup_logging(BUYER_NAME, "oden-producer")
CLUSTER_ID = cluster_config.get_cluster_id(BUYER_NAME)
logger.info(f"Buyer node '{BUYER_NAME}' resolved to cluster {CLUSTER_ID}")

producer = KafkaTxProducer(KAFKA_BOOTSTRAP_SERVERS, logger)
producer.ensure_topic(CLUSTER_ID)


if __name__ == "__main__":
    try:
        app.run(debug=False, use_reloader=False, host="0.0.0.0", port=5665)
    finally:
        producer.flush()
