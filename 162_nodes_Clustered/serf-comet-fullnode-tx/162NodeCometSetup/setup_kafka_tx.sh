#!/bin/bash

# List of containers (Ubuntu nodes)
containers=()
for i in {1..162}; do
  containers+=(clab-nebula-extended-serf"$i")
done

setup_kafka() {
  for container in "${containers[@]}"; do

    # Get IP address of eth1
    docker exec "$container" sysctl -w net.ipv6.conf.all.disable_ipv6=1
    ip_address=$(docker exec "$container" ip -4 addr show eth1 | grep -oP '(?<=inet\s)\d+\.\d+\.\d+\.\d+')
    if [ -z "$ip_address" ]; then
      echo "Failed to retrieve IP address for $container"
      continue
    fi
    echo "IP address for $container (eth1): $ip_address"
    
    # Install Redis
    docker exec "$container" bash -c "
    rm -f /etc/apt/sources.list.d/redis.list
    set -e 
    apt-get update
    apt-get install -y software-properties-common
    add-apt-repository universe
    apt-get update
    apt-get install -y redis-server
    redis-server --daemonize yes
    "
    rVersion=$(docker exec "$container" redis-server --version)
    echo "Redis $rVersion installation complete."

    docker exec "$container" bash -c "cd /root && mkdir -p logs && mkdir -p computetx"
    
    # Install Python
    echo "Installing Python..."
    docker exec "$container" bash -c "DEBIAN_FRONTEND=noninteractive apt update && apt upgrade -y && apt install -y python3 python3-pip && pip3 install --no-cache-dir flask requests redis confluent-kafka python-logging-loki"
    pVersion=$(docker exec "$container" python3 --version)
    echo "$pVersion installation complete."
    echo "Copying tx client..."
    docker cp "./computetx/." "$container":/root/computetx/ || { echo "Failed to copy py files to $container"; exit 1; }

    echo "Transaction Setup in $container is complete."
    
  done
}

setup_kafka
