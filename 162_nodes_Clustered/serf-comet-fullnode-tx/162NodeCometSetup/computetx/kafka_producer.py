"""
Thin wrapper around confluent_kafka.Producer for the ODEN buyer nodes.

- OnGoing transactions: produced with key = f"{tx_uuid}-{seller_name}".
  Kafka's default (murmur2) key hash spreads these across the topic's
  partitions; no need to pick a partition number ourselves.
- Failed transactions: there's no seller to key on, so we explicitly assign
  a partition number using a simple round-robin counter that's local to
  each topic.

One Producer instance is shared across all clusters this process might
serve (normally just one, since each buyer node lives in exactly one
cluster) -- creating a new confluent_kafka.Producer per request would be
wasteful, it's designed to be long-lived.
"""

from __future__ import annotations

import itertools
import threading
from typing import Any

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

import cluster_config


class KafkaTxProducer:
    def __init__(self, bootstrap_servers: str, logger):
        self._logger = logger
        self._producer = Producer({
            "bootstrap.servers": bootstrap_servers,
            "acks": "all",
            "enable.idempotence": True,
            "retries": 5,
            "linger.ms": 20,
        })
        self._admin = AdminClient({"bootstrap.servers": bootstrap_servers})
        self._rr_counters: dict[str, itertools.cycle] = {}
        self._lock = threading.Lock()

    def ensure_topic(self, cluster_id: int) -> None:
        """Create the cluster's topic with the correct partition count if it
        doesn't already exist. Safe to call repeatedly (no-op if present)."""
        topic = cluster_config.get_topic(cluster_id)
        partitions = cluster_config.get_partition_count(cluster_id)
        existing = self._admin.list_topics(timeout=10).topics
        if topic in existing:
            return
        new_topic = NewTopic(topic, num_partitions=partitions, replication_factor=1)
        futures = self._admin.create_topics([new_topic])
        for t, fut in futures.items():
            try:
                fut.result()
                self._logger.info(f"Created Kafka topic '{t}' with {partitions} partitions")
            except Exception as exc:
                # Race with another buyer node creating it simultaneously is fine.
                if "already exists" not in str(exc).lower():
                    self._logger.error(f"Failed creating topic '{t}': {exc}")

    def _next_round_robin_partition(self, topic: str, num_partitions: int) -> int:
        with self._lock:
            if topic not in self._rr_counters:
                self._rr_counters[topic] = itertools.cycle(range(num_partitions))
            return next(self._rr_counters[topic])

    def produce_ongoing(self, cluster_id: int, tx_uuid: str, seller_name: str, value: dict[str, Any]) -> None:
        topic = cluster_config.get_topic(cluster_id)
        partition = cluster_config.get_partition_for_seller(cluster_id, seller_name)
        key = f"{tx_uuid}-{seller_name}"
        self._produce(topic, key=key, value=value, partition=partition)

    def produce_failed(self, cluster_id: int, tx_uuid: str, value: dict[str, Any]) -> None:
        topic = cluster_config.get_topic(cluster_id)
        num_partitions = cluster_config.get_partition_count(cluster_id)
        partition = self._next_round_robin_partition(topic, num_partitions)
        self._produce(topic, key=tx_uuid, value=value, partition=partition)

    def _produce(self, topic: str, key: str, value: dict[str, Any], partition: int | None = None) -> None:
        import json

        def _on_delivery(err, msg):
            if err is not None:
                self._logger.error(f"Kafka delivery failed for topic={topic} key={key}: {err}")
            else:
                self._logger.info(
                    f"Delivered to Kafka topic={msg.topic()} partition={msg.partition()} "
                    f"offset={msg.offset()} key={key}"
                )

        kwargs = {"topic": topic, "key": key.encode("utf-8"), "value": json.dumps(value).encode("utf-8"),
                  "callback": _on_delivery}
        if partition is not None:
            kwargs["partition"] = partition
        self._producer.produce(**kwargs)
        self._producer.poll(0)

    def flush(self, timeout: float = 10.0) -> None:
        self._producer.flush(timeout)
