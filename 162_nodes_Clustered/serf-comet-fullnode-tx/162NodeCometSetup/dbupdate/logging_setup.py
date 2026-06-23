"""
logging_setup.py
Structured JSON logging that pushes straight to Loki -- no Promtail,
no sidecar, no extra containers. Same pattern as your ODEN producer
logging: one handler, set LOKI_URL, done.

If LOKI_URL is not set, logs just go to stdout as JSON (still readable,
still grep/jq-able, just not shipped anywhere).
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
import logging_loki
import queue

SERVICE_NAME = os.environ.get("SERVICE_NAME", "oden-tx-history-scheduler")
LOKI_URL = os.environ.get("LOKI_URL", "http://loki:3100/loki/api/v1/push")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        payload = {
            "timestamp": ts,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": SERVICE_NAME,
        }
        # Any extra fields passed via logger.info("msg", extra={"id": 5, ...})
        # get merged in directly, so call sites can attach whatever
        # structured context is relevant (id, uuid, tx_hash, row_count, etc).
        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_FIELDS or key in payload:
                continue
            payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


# Standard logging.LogRecord attributes -- anything NOT in this set was
# passed in via `extra=` and should be included in the JSON payload.
_STANDARD_RECORD_FIELDS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName",
}

_configured = False


def setup_logging():
    """Call once at process startup. Idempotent."""
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)
    root.handlers.clear()

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(JsonFormatter())
    root.addHandler(stream_handler)

    if LOKI_URL:
        try:
            loki_handler = logging_loki.LokiQueueHandler(
                queue.Queue(-1),
                url=LOKI_URL,
                tags={"job": SERVICE_NAME},
                version="1",
            )
            loki_handler.handler.setFormatter(JsonFormatter())
            loki_handler.handler.handleError = lambda record: None
            root.addHandler(loki_handler)
            logging.getLogger(__name__).info(
                "Loki direct-push handler attached", extra={"loki_url": LOKI_URL}
            )
        except ImportError:
            logging.getLogger(__name__).warning(
                "LOKI_URL is set but python-logging-loki isn't installed; "
                "falling back to stdout-only JSON logs."
            )
        except Exception:
            logging.getLogger(__name__).exception(
                "Failed to attach Loki handler; continuing with stdout-only logs."
            )

    # Keep noisy third-party loggers from drowning out real signal.
    logging.getLogger("werkzeug").setLevel(os.environ.get("WERKZEUG_LOG_LEVEL", "INFO"))
    logging.getLogger("apscheduler").setLevel(os.environ.get("APSCHEDULER_LOG_LEVEL", "WARNING"))
