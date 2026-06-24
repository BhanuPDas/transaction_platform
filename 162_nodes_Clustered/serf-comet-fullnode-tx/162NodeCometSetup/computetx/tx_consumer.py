"""
Run one of these per seller node. It:

  1. Reads this node's identity from node.json (NODE_JSON_PATH).
  2. Looks up which cluster/topic/partition that node owns as a seller
     (mirrors the producer's partitioning: a seller only ever receives
     messages on its own partition -- OnGoing txs keyed to it directly,
     Failed txs landing there via the producer's round-robin).
  3. Manually assigns the consumer to that single partition (no consumer
     group rebalancing -- the assignment is deterministic from topology).
  4. For each message: parses the tx event JSON and persists it
       - status == "Failed"  -> tx_history only
       - status == "OnGoing" -> tx_balance (buyer -amount, seller +amount)
                                 + tx_history, in one DB transaction, then
                                 best-effort publish to the Redis "emulate"
                                 stream.
  5. Commits the Kafka offset only after the DB write succeeds, so a crash
     mid-processing replays that message on restart instead of losing it.

Config via environment variables:
    NODE_JSON_PATH          default: /opt/serfapp/node.json
    KAFKA_BOOTSTRAP_SERVERS default: kafka:9092
    TX_DB_DSN               default: dbname=oden user=oden password=changeme host=db port=5432
    DB_POOL_MIN             default: 1   (connections kept open per process)
    DB_POOL_MAX             default: 3   (hard cap per process)
    KAFKA_GROUP_ID_PREFIX   default: oden.cluster  (final group.id is
                                       f"{prefix}.{node_name}")
"""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from typing import Any
import logging
from confluent_kafka import Consumer, KafkaError, TopicPartition
import push_to_redis
import cluster_config
import logging_setup
from db_handler import DBHandler
import sellers_discovery

NODE_JSON_PATH = os.environ.get("NODE_JSON_PATH", "/opt/serfapp/node.json")
BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
DB_DSN = os.environ.get(
    "TX_DB_DSN", "dbname=oden user=oden password=changeme host=db port=5432"
)
GROUP_ID_PREFIX = os.environ.get("KAFKA_GROUP_ID_PREFIX", "oden.cluster")
DB_POOL_MIN = int(os.environ.get("DB_POOL_MIN", "1"))
DB_POOL_MAX = int(os.environ.get("DB_POOL_MAX", "3"))

# Failed processing of a message is retried in-process before giving up the
# poll loop iteration, to avoid a tight spin on a transient DB outage.
_RETRY_SLEEP_SECONDS = 2.0

def get_node_name(json_path: str) -> str:
    with open(json_path, "r") as file:
        data = json.load(file)
    node_name = data.get("node_name")
    if node_name is None:
        raise KeyError(f"Key 'node_name' not found in {json_path}")
    return node_name

class TxConsumer:
    def __init__(
        self,
        node_name: str,
        bootstrap_servers: str,
        db_dsn: str,
        logger: logging.LoggerAdapter,
        db_pool_min: int = 1,
        db_pool_max: int = 3,
    ):
        self.logger = logger
        self.node_name = node_name
        self.cluster_id = cluster_config.get_cluster_id(self.node_name)

        # This will raise UnknownNodeError if node_name isn't a seller in its
        # cluster -- intentional: only seller nodes own a partition to read.
        self.partition = cluster_config.get_partition_for_seller(
            self.cluster_id, self.node_name
        )
        self.topic = cluster_config.get_topic(self.cluster_id)

        group_id = f"{GROUP_ID_PREFIX}.{self.node_name}"
        self._consumer = Consumer({
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        })
        self._db = DBHandler(db_dsn, logger=self.logger, minconn=db_pool_min, maxconn=db_pool_max)
        self._running = False

        self.logger.info(
            "Initialized consumer for node=%s cluster=%s topic=%s partition=%s group_id=%s",
            self.node_name, self.cluster_id, self.topic, self.partition, group_id,
        )

    def _resume_from_committed_or_start(self) -> None:
        tp = TopicPartition(self.topic, self.partition)
        self._consumer.assign([tp])

        committed = self._consumer.committed([tp], timeout=10)
        if committed and committed[0].offset >= 0:
            self.logger.info(
                "Resuming topic=%s partition=%s from committed offset=%s",
                self.topic, self.partition, committed[0].offset,
            )
        else:
            self.logger.info(
                "No committed offset for topic=%s partition=%s, starting per auto.offset.reset",
                self.topic, self.partition,
            )

    def run(self) -> None:
        self._resume_from_committed_or_start()
        self._running = True

        def _handle_signal(signum, _frame):
            self.logger.info("Received signal %s, shutting down", signum)
            self._running = False

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

        try:
            while self._running:
                msg = self._consumer.poll(timeout=1.0)
                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    self.logger.error("Kafka error: %s", msg.error())
                    continue

                self._handle_message(msg)
        finally:
            self._db.close()
            self._consumer.close()
            self.logger.info("Consumer for node=%s stopped", self.node_name)

    def _handle_message(self, msg) -> None:
        raw_value = msg.value()
        try:
            event: dict[str, Any] = json.loads(raw_value)
        except (json.JSONDecodeError, TypeError) as exc:
            # Poison message: log and skip it (commit past it) rather than
            # blocking the partition forever on something we can never parse.
            self.logger.error(
                "Skipping unparsable message at offset=%s: %s", msg.offset(), exc
            )
            self._consumer.commit(message=msg,asynchronous=True)
            return

        status = event.get("status")

        # Retry loop for transient failures (e.g. DB hiccup). We don't commit
        # until persistence succeeds, so on a hard crash this message is
        # simply replayed from the last committed offset on restart.
        while self._running:
            try:
                if status == "Failed":
                    self._db.persist_failed(event)
                    sellers_discovery.notify_fail_tx_buyer(event, self.logger)
                elif status == "OnGoing":
                    self._db.persist_ongoing(event)
                    push_to_redis.publish_ongoing_to_redis(event, logger=self.logger)
                else:
                    self.logger.warning(
                        "Unknown status %r at offset=%s, persisting nothing",
                        status, msg.offset(),
                    )
                self._consumer.commit(message=msg, asynchronous=True)
                return
            except Exception as exc:
                self.logger.error(f"Error while processing events{exc}")
                self.logger.exception(
                    "Failed processing message at offset=%s, retrying in %ss",
                    msg.offset(), _RETRY_SLEEP_SECONDS,
                )
                time.sleep(_RETRY_SLEEP_SECONDS)


def main() -> None:
    node_name = get_node_name(NODE_JSON_PATH)
    logger = logging_setup.setup_logging(node_name, "oden-consumer")

    cluster_id = cluster_config.get_cluster_id(node_name)
    logger.info("Seller node '%s' resolved to cluster %s", node_name, cluster_id)

    consumer = TxConsumer(
        node_name,
        BOOTSTRAP_SERVERS,
        DB_DSN,
        logger,
        db_pool_min=DB_POOL_MIN,
        db_pool_max=DB_POOL_MAX,
    )
    consumer.run()


if __name__ == "__main__":
    sys.exit(main())
