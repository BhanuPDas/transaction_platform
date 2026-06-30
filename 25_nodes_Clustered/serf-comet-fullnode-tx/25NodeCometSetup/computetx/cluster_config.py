"""
Topic / partition model
------------------------
Each cluster gets its own Kafka topic, with partition count == number of
sellers in that cluster:

    Cluster 1:  2 sellers -> 2 partitions
    Cluster 2:  3 sellers -> 3 partitions

"OnGoing" transactions are keyed by `f"{uuid}-{seller_name}"`, which Kafka's
default partitioner hashes across the topic's partitions. "Failed"
transactions (no seller found / insufficient budget) have no seller to key
on, so they're spread round-robin across the topic's partitions instead.
"""

from __future__ import annotations

TOPIC_PREFIX = "oden.cluster"

# cluster_id -> every serf node name in that cluster (buyers + sellers)
CLUSTER_NODES = {
    1: ['serf1', 'serf2', 'serf3', 'serf4', 'serf5', 'serf6', 'serf7', 'serf8', 'serf9', 'serf10', 'serf11', 'serf12'],
    2: ['serf13', 'serf14', 'serf15', 'serf16', 'serf17', 'serf18', 'serf19', 'serf20', 'serf21', 'serf22', 'serf23', 'serf24', 'serf25'],
}

# cluster_id -> serf nodes in that cluster that act as sellers (consumers)
CLUSTER_SELLERS = {
    1: ['serf1', 'serf5'],
    2: ['serf13', 'serf14', 'serf15'],
}

# Reverse index, built once at import time: node_name -> cluster_id
_NODE_TO_CLUSTER = {
    node: cid for cid, nodes in CLUSTER_NODES.items() for node in nodes
}


class UnknownNodeError(KeyError):
    """Raised when a node name isn't present in any known cluster."""


def get_cluster_id(node_name: str) -> int:
    """Look up which cluster a given serf node belongs to."""
    try:
        return _NODE_TO_CLUSTER[node_name]
    except KeyError as exc:
        raise UnknownNodeError(
            f"Node '{node_name}' is not present in any configured cluster. "
            "Check cluster_config.py against the current topology."
        ) from exc


def get_topic(cluster_id: int) -> str:
    return f"{TOPIC_PREFIX}.{cluster_id}"


def get_partition_count(cluster_id: int) -> int:
    return len(CLUSTER_SELLERS[cluster_id])


def get_sellers(cluster_id: int) -> list[str]:
    return CLUSTER_SELLERS[cluster_id]

def get_partition_for_seller(cluster_id: int, seller_name: str) -> int:
    sellers = CLUSTER_SELLERS[cluster_id]
    try:
        return sellers.index(seller_name)
    except ValueError as exc:
        raise UnknownNodeError(
            f"Seller '{seller_name}' is not a configured seller in cluster {cluster_id}. "
            f"Known sellers: {sellers}"
        ) from exc

