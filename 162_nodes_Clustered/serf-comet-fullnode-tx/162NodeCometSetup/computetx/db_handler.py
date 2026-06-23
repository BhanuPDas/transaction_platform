"""
Tables (as already migrated via the ALTER TABLE statements you have):

    public.tx_history
        id            bigserial PRIMARY KEY   -- auto-increments, never set explicitly
        uuid          varchar(36) -- widened to fit str(uuid.uuid4())
        status        varchar(10)
        tx_msg        varchar(1200)
        tx_start_ts   timestamptz
        tx_end_unix   bigint
        last_updated  timestamptz

    public.tx_balance
        id            serial PRIMARY KEY      -- auto-increments, never set explicitly
        node          varchar(7) NOT NULL
        amount        bigint NOT NULL DEFAULT 0
        last_updated  timestamptz

NOTE on tx_balance: all 162 nodes already exist as rows (node + amount only,
nothing is ever inserted), so every adjustment is a plain
`UPDATE ... SET amount = amount + %s WHERE node = %s`. A single UPDATE
statement is already atomic at the row level in Postgres -- no extra locking
needed -- so concurrent adjustments from different consumer processes are
safe as-is. If an UPDATE affects 0 rows, that means the node name in the
event doesn't match any seeded row, which is treated as an error rather than
silently inserting a new one.

CONNECTION POOLING:
DBHandler owns a bounded psycopg2 ThreadedConnectionPool rather than a single
long-lived connection. Each persist_* call checks out a connection, does its
work in one transaction, and always returns the connection -- discarding it
instead of returning it if it turned out to be broken, so a dead connection
is never recycled back into the pool and silently reused.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional, Union

import psycopg2
from psycopg2 import pool as psycopg2_pool

_TX_MSG_MAX_LEN = 1200


def _parse_ts(value: Optional[str], logger) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp string (e.g. tx_start_ts). Returns None for
    missing/empty/unparsable values rather than raising, since tx_end_ts is
    sometimes an empty string in the payload."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        logger.warning("Could not parse timestamp %r", value)
        return None


def _build_tx_msg(event: dict[str, Any]) -> str:
    """Build the tx_msg column content: a compact JSON dump of the whole
    event, truncated to fit the column."""
    payload = json.dumps(event)
    return payload[:_TX_MSG_MAX_LEN]


def _get_uuid(event: dict[str, Any]) -> str:
    return event.get("tx_hash") or ""


class DBHandler:
    """Pooled, transactional persistence for tx events.

    One DBHandler is meant to be owned by one consumer process (one seller
    node's partition loop). It holds a small bounded connection pool rather
    than a single long-lived connection, so repeated transient failures
    can't accumulate open connections over time.
    """

    def __init__(
        self,
        dsn: str,
        logger: logging.LoggerAdapter,
        minconn: int = 1,
        maxconn: int = 3,
    ):
        self._dsn = dsn
        self.logger = logger
        self._pool = psycopg2_pool.ThreadedConnectionPool(minconn, maxconn, dsn)
        self.logger.info("Initialized DB connection pool (min=%s, max=%s)", minconn, maxconn)

    def close(self) -> None:
        self._pool.closeall()

    # ------------------------------------------------------------------ #
    # Failed transactions
    # ------------------------------------------------------------------ #
    def persist_failed(self, event: dict[str, Any]) -> None:
        uuid = _get_uuid(event)
        tx_msg = _build_tx_msg(event)
        tx_start_ts = _parse_ts(event.get("tx", {}).get("tx_start_ts"), logger=self.logger)
        tx_end_unix = event.get("tx_end_unix")

        conn = self._pool.getconn()
        broken = False
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.tx_history
                            (uuid, status, tx_msg, tx_start_ts, tx_end_unix, last_updated)
                        VALUES (%s, %s, %s, %s, %s, now())
                        """,
                        (uuid, "Failed", tx_msg, tx_start_ts, tx_end_unix),
                    )
            self.logger.info("Persisted Failed tx uuid=%s", uuid)
        except Exception:
            broken = True
            raise
        finally:
            self._pool.putconn(conn, close=broken)

    # ------------------------------------------------------------------ #
    # OnGoing transactions
    # ------------------------------------------------------------------ #
    def persist_ongoing(self, event: dict[str, Any]) -> None:
        tx = event.get("tx", {})
        buyer = tx.get("buyer", {})
        seller = tx.get("seller", {})
        buyer_name = buyer.get("name")
        seller_name = seller.get("name")
        amount = tx.get("amount")

        if not buyer_name or not seller_name or amount is None:
            raise ValueError(f"OnGoing event missing buyer/seller/amount: {event!r}")

        uuid = _get_uuid(event)
        tx_msg = _build_tx_msg(event)
        tx_start_ts = _parse_ts(tx.get("tx_start_ts"), logger=self.logger)
        tx_end_unix = event.get("tx_end_unix")

        conn = self._pool.getconn()
        broken = False
        try:
            with conn:  # single transaction: both balances + history row
                with conn.cursor() as cur:
                    self._adjust_balance(cur, buyer_name, -amount)
                    self._adjust_balance(cur, seller_name, amount)
                    cur.execute(
                        """
                        INSERT INTO public.tx_history
                            (uuid, status, tx_msg, tx_start_ts, tx_end_unix, last_updated)
                        VALUES (%s, %s, %s, %s, %s, now())
                        """,
                        (uuid, "OnGoing", tx_msg, tx_start_ts, tx_end_unix),
                    )
            self.logger.info(
                "Persisted OnGoing tx uuid=%s buyer=%s(-%s) seller=%s(+%s)",
                uuid, buyer_name, amount, seller_name, amount,
            )
        except Exception:
            broken = True
            raise
        finally:
            self._pool.putconn(conn, close=broken)

    @staticmethod
    def _adjust_balance(cur, node_name: str, delta: int) -> None:
        # tx_balance is pre-seeded with all 162 nodes, so this is always an
        # UPDATE, never an INSERT. The UPDATE itself is atomic at the row
        # level in Postgres, so concurrent adjustments to the same node from
        # different consumer processes are safe without any extra locking.
        cur.execute(
            """
            UPDATE public.tx_balance
            SET amount = amount + %s, last_updated = now()
            WHERE node = %s
            """,
            (delta, node_name),
        )
        if cur.rowcount == 0:
            raise ValueError(
                f"tx_balance has no row for node={node_name!r}; "
                "expected all 162 nodes to be pre-seeded"
            )
