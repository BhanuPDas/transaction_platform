#!/bin/bash
set -e

BROKER="localhost:9092"   # inside the container, the broker is local

# Partition count = seller count per cluster, verified against S (48 sellers)
# and clusters.xlsx (162 nodes / 8 clusters):
#   Cluster 1:  5 sellers → 5 partitions
#   Cluster 2:  4 sellers → 4 partitions
#   Cluster 3:  3 sellers → 3 partitions
#   Cluster 4:  6 sellers → 6 partitions
#   Cluster 5:  9 sellers → 9 partitions
#   Cluster 6:  9 sellers → 9 partitions
#   Cluster 7: 11 sellers → 11 partitions
#   Cluster 8:  1 seller  → 1 partition

declare -A PARTITIONS=(
  [1]=2 [2]=3
)

echo "=== Creating ODEN Kafka topics ==="
echo "Broker: $BROKER"
echo ""

TOPICS=()
for CLUSTER_ID in 1 2; do
  TOPIC="oden.cluster.${CLUSTER_ID}"
  TOPICS+=("$TOPIC")
  PARTS="${PARTITIONS[$CLUSTER_ID]}"

  echo "Creating $TOPIC ($PARTS partitions)..."
  /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server "$BROKER" \
    --create \
    --if-not-exists \
    --topic "$TOPIC" \
    --partitions "$PARTS" \
    --replication-factor 1

  if [ $? -eq 0 ]; then
    echo "  ✓ $TOPIC created"
  else
    echo "  ✗ Failed to create $TOPIC"
  fi
done

echo ""
echo "=== All topics ==="
/opt/kafka/bin/kafka-topics.sh --bootstrap-server "$BROKER" --list

echo ""
echo "=== Topic details ==="
for TOPIC in "${TOPICS[@]}"; do
  /opt/kafka/bin/kafka-topics.sh --bootstrap-server "$BROKER" --describe --topic "$TOPIC"
done