"""
wsgi.py
Entrypoint for gunicorn. Sets up logging, the DB pool, and the
scheduler, then exposes `app` for gunicorn to serve.
"""

import logging

from logging_setup import setup_logging
setup_logging()

import db
import scheduler
from app import app

logger = logging.getLogger(__name__)

db.init_pool()
scheduler.start_scheduler()

logger.info("App ready")
