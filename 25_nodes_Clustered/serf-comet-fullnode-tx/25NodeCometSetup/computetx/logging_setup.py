"""
Structured logging for Loki ingestion.

Every log record gets a `buyer` field (the node name of this serf node) so
that logs from all 162 nodes can be filtered/traced individually in Grafana,
e.g.  `{job="oden-producer"} | json | buyer="serf12"`.

Two output paths, both usable at once:
  1. JSON lines on stdout -> scraped by Promtail/Grafana Agent (recommended,
     no extra network dependency, matches your existing Loki/Grafana stack).
  2. Optional direct push to Loki's HTTP API if LOKI_URL is set, using
     `logging-loki` (pip install python-logging-loki) -- handy if you don't
     want to run a separate log-shipping agent on every node.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
import logging_loki  # pip install python-logging-loki


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        payload = {
            "timestamp": ts,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "buyer": getattr(record, "buyer", "unknown"),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging(node_name: str, job_type: str) -> logging.LoggerAdapter:
    """
    Configure root logging once and return a LoggerAdapter that
    automatically injects `buyer=<node_name>` into every record, so call
    sites never need to remember to pass it themselves.
    """
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(JsonFormatter())
    root.addHandler(stream_handler)

    loki_url = os.environ.get("LOKI_URL", "http://loki:3100/loki/api/v1/push")
    if loki_url:
        try:
            loki_handler = logging_loki.LokiHandler(
                url=loki_url,
                tags={"job": job_type, "buyer": node_name},
                version="1",
            )
            loki_handler.setFormatter(JsonFormatter())
            root.addHandler(loki_handler)
        except ImportError:
            logging.getLogger(__name__).warning(
                "LOKI_URL is set but python-logging-loki isn't installed; "
                "falling back to stdout-only JSON logs for Promtail to scrape."
            )

    base_logger = logging.getLogger(job_type)
    return logging.LoggerAdapter(base_logger, {"buyer": node_name})
