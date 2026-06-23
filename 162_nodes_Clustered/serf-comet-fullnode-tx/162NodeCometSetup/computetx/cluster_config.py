"""
Topic / partition model
------------------------
Each cluster gets its own Kafka topic, with partition count == number of
sellers in that cluster:

    Cluster 1:  5 sellers -> 5 partitions
    Cluster 2:  4 sellers -> 4 partitions
    Cluster 3:  3 sellers -> 3 partitions
    Cluster 4:  6 sellers -> 6 partitions
    Cluster 5:  9 sellers -> 9 partitions
    Cluster 6:  9 sellers -> 9 partitions
    Cluster 7: 11 sellers -> 11 partitions
    Cluster 8:  1 seller  -> 1 partition

"OnGoing" transactions are keyed by `f"{uuid}-{seller_name}"`, which Kafka's
default partitioner hashes across the topic's partitions. "Failed"
transactions (no seller found / insufficient budget) have no seller to key
on, so they're spread round-robin across the topic's partitions instead.
"""

from __future__ import annotations

TOPIC_PREFIX = "oden-tx-cluster"

# cluster_id -> every serf node name in that cluster (buyers + sellers)
CLUSTER_NODES = {
    1: ['serf1', 'serf2', 'serf3', 'serf4', 'serf5', 'serf6', 'serf7', 'serf8', 'serf9', 'serf10', 'serf11', 'serf12', 'serf13', 'serf14', 'serf15', 'serf16', 'serf17'],
    2: ['serf18', 'serf19', 'serf20', 'serf21', 'serf22', 'serf23', 'serf24', 'serf25', 'serf26', 'serf27', 'serf28', 'serf29', 'serf30', 'serf31', 'serf32'],
    3: ['serf33', 'serf34', 'serf35', 'serf36', 'serf37', 'serf38', 'serf39', 'serf40', 'serf41', 'serf42'],
    4: ['serf43', 'serf44', 'serf45', 'serf46', 'serf47', 'serf48', 'serf49', 'serf50', 'serf57', 'serf58', 'serf59', 'serf60', 'serf61', 'serf62', 'serf63', 'serf64', 'serf65', 'serf82'],
    5: ['serf66', 'serf67', 'serf68', 'serf69', 'serf70', 'serf71', 'serf72', 'serf73', 'serf74', 'serf75', 'serf76', 'serf77', 'serf78', 'serf79', 'serf80', 'serf81', 'serf83', 'serf84', 'serf85', 'serf86', 'serf87', 'serf88', 'serf89', 'serf90', 'serf91', 'serf92', 'serf93', 'serf94', 'serf95'],
    6: ['serf96', 'serf97', 'serf98', 'serf99', 'serf100', 'serf101', 'serf102', 'serf103', 'serf104', 'serf105', 'serf106', 'serf107', 'serf108', 'serf109', 'serf110', 'serf111', 'serf112', 'serf113', 'serf114', 'serf115', 'serf116', 'serf117', 'serf118', 'serf119', 'serf120', 'serf121', 'serf122', 'serf123', 'serf124', 'serf125', 'serf126', 'serf128', 'serf129'],
    7: ['serf127', 'serf130', 'serf131', 'serf132', 'serf133', 'serf134', 'serf135', 'serf136', 'serf137', 'serf138', 'serf139', 'serf140', 'serf141', 'serf142', 'serf143', 'serf144', 'serf145', 'serf146', 'serf147', 'serf148', 'serf149', 'serf150', 'serf151', 'serf152', 'serf153', 'serf154', 'serf155', 'serf156', 'serf157', 'serf158', 'serf159', 'serf160', 'serf161', 'serf162'],
    8: ['serf51', 'serf52', 'serf53', 'serf54', 'serf55', 'serf56'],
}

# cluster_id -> serf nodes in that cluster that act as sellers (consumers)
CLUSTER_SELLERS = {
    1: ['serf3', 'serf6', 'serf9', 'serf12', 'serf16'],
    2: ['serf19', 'serf22', 'serf25', 'serf30'],
    3: ['serf33', 'serf36', 'serf39'],
    4: ['serf44', 'serf47', 'serf50', 'serf58', 'serf61', 'serf64'],
    5: ['serf67', 'serf72', 'serf75', 'serf78', 'serf81', 'serf86', 'serf89', 'serf92', 'serf95'],
    6: ['serf100', 'serf103', 'serf106', 'serf109', 'serf114', 'serf117', 'serf120', 'serf123', 'serf128'],
    7: ['serf131', 'serf134', 'serf137', 'serf142', 'serf145', 'serf148', 'serf151', 'serf156', 'serf158', 'serf160', 'serf162'],
    8: ['serf53'],
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
    return f"{TOPIC_PREFIX}-{cluster_id}"


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

