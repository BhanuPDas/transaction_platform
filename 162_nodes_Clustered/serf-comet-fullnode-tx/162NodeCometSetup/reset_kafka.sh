#!/bin/bash

declare -A SELLER_NODES=(
    [3]=1   [6]=1   [9]=1   [12]=1  [16]=1  [19]=1  [22]=1  [25]=1
    [30]=1  [33]=1  [36]=1  [39]=1  [44]=1  [47]=1  [50]=1  [53]=1
    [58]=1  [61]=1  [64]=1  [67]=1  [72]=1  [75]=1  [78]=1  [81]=1
    [86]=1  [89]=1  [92]=1  [95]=1  [100]=1 [103]=1 [106]=1 [109]=1
    [114]=1 [117]=1 [120]=1 [123]=1 [128]=1 [131]=1 [134]=1 [137]=1
    [142]=1 [145]=1 [148]=1 [151]=1 [156]=1 [158]=1 [160]=1 [162]=1
)
# List of containers
containers=()
for i in {1..162}; do
  containers+=(clab-nebula-extended-serf"$i")
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
    docker exec "$container" bash -c "DEBIAN_FRONTEND=noninteractive apt update && apt upgrade -y && pip3 install --no-cache-dir confluent-kafka python-logging-loki psycopg2-binary"
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
