"""
app.py
Flask API exposing GET endpoints for tx_history records.
"""

import logging
import time
from flask import Flask, jsonify
import db

logger = logging.getLogger(__name__)
app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    try:
        with db.get_cursor(dict_cursor=False) as cur:
            cur.execute("SELECT 1;")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.exception("Health check failed")
        return jsonify({"status": "error", "detail": str(e)}), 503


@app.route("/tx_history", methods=["GET"])
def get_tx_messages_only():
    """Return only tx_msg values for the latest 2000 records by tx_end_unix."""
    start = time.monotonic()
    try:
        with db.get_cursor(dict_cursor=True) as cur:
            cur.execute(
                """
                SELECT tx_msg
                FROM public.tx_history
                ORDER BY tx_end_unix DESC
                LIMIT 2000;
                """
            )
            messages = [row["tx_msg"] for row in cur.fetchall()]

        logger.info(
            "GET /tx_history",
            extra={"row_count": len(messages), "elapsed_ms": round((time.monotonic() - start) * 1000, 1)},
        )
        return jsonify({"count": len(messages), "tx_msg": messages}), 200

    except Exception as e:
        logger.exception("Failed to fetch tx_msg column")
        return jsonify({"error": "failed to fetch tx_msg", "detail": str(e)}), 500
