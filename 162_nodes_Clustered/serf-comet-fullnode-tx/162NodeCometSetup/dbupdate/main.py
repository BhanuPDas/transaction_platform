"""
main.py
Local-dev entrypoint (runs Flask's dev server directly, no gunicorn).
For production/Docker, use wsgi.py via gunicorn instead -- see Dockerfile.
"""

import logging
import os

from logging_setup import setup_logging
setup_logging()

import db
import scheduler
from app import app

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    db.init_pool()
    scheduler.start_scheduler()
    logger.info("App ready (local dev mode)")

    app.run(
        host=os.environ.get("FLASK_HOST", "0.0.0.0"),
        port=int(os.environ.get("FLASK_PORT", "5000")),
    )
