#!/bin/bash

declare -A SELLER_NODES=(
    [1]=1   [5]=1   [13]=1   [14]=1  [15]=1
)
# List of containers
containers=()
for i in {1..25}; do
  containers+=(clab-century-serf"$i")
done

reset_kafka() {
  for i in "${!containers[@]}"; do
    container="${containers[$i]}"
    k=$((i + 1))
    ip_address=$(docker exec "$container" ip -4 addr show eth1 | grep -oP '(?<=inet\s)\d+\.\d+\.\d+\.\d+')
    if [ -z "$ip_address" ]; then
      echo "Failed to retrieve IP address for $container"
      continue
    fi
    echo "IP address for $container (eth1): $ip_address"
    echo "=============================================="
    echo "Resetting Kafka on $container..."
    echo "=============================================="
    echo "[1] Killing Kafka Tx Producer..."
    tx_pid=$(docker exec "$container" pgrep -f "python3 tx_producer.py")
    if [[ -n "$tx_pid" ]]; then
      docker exec "$container" kill -9 "$tx_pid"
      sleep 1
    else
      echo "Python Tx Producer not running"
    fi

    echo "[2] Killing Kafka Tx Consumer..."
    tx_pid=$(docker exec "$container" pgrep -f "python3 tx_consumer.py")
    if [[ -n "$tx_pid" ]]; then
      docker exec "$container" kill -9 "$tx_pid"
      sleep 1
    else
      echo "Python Tx Consumer not running"
    fi

    echo "[3] Restarting Producers And Consumers..."
#    docker exec "$container" bash -c "DEBIAN_FRONTEND=noninteractive apt update && apt upgrade -y && pip3 install --no-cache-dir confluent-kafka python-logging-loki psycopg2-binary"
    docker exec "$container" bash -c "cd /root && rm -rf computetx"
    docker cp "./computetx/." "$container":/root/computetx/ || { echo "Failed to copy py files to $container"; exit 1; }
    if [[ -n "${SELLER_NODES[$k]}" ]]; then
      docker exec -d "$container" bash -c "cd /root/computetx && nohup python3 tx_consumer.py > /dev/null 2>&1 &"
    else
      docker exec -d "$container" bash -c "cd /root/computetx && nohup python3 tx_producer.py > /dev/null 2>&1 &"
    fi
    echo "✔ Done with $container"
  done
}

reset_kafka
