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
  containers+=(clab-nebula-extended-serf$i)
done

reset_cometbft() {
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
    echo "Resetting ABCI + CometBFT on $container..."
    echo "=============================================="

    echo "[1] Killing CometBFT..."
    comet_pid=$(docker exec "$container" pgrep -f "/root/go/bin/cometbft node")
    if [[ -n "$comet_pid" ]]; then
      docker exec "$container" kill -9 $comet_pid
      sleep 1
    else
      echo "CometBFT not running"
    fi

    echo "[2] Killing ABCI..."
    abci_pid=$(docker exec "$container" pgrep -f "/root/abci-app")
    if [[ -n "$abci_pid" ]]; then
      docker exec "$container" kill -9 $abci_pid
      sleep 1
    else
      echo "ABCI not running"
    fi
    echo "[3] Killing Tx API..."
    tx_pid=$(docker exec "$container" pgrep -f "python3 tx_api.py")
    if [[ -n "$tx_pid" ]]; then
      docker exec "$container" kill -9 $tx_pid
      sleep 1
    else
      echo "Python Tx API not running"
    fi

    echo "[4] Removing state.db..."
    docker exec "$container" rm -rf /root/abci/state.db
    sleep 1

    echo "[5] Resetting CometBFT state..."
    docker exec "$container" /root/go/bin/cometbft unsafe-reset-all
    sleep 1

    echo "[6] Restarting ABCI & CometBFT..."
    docker exec "$container" bash -c "cd /root && rm -rf abci && mkdir -p abci && rm -rf cometclient && mkdir -p cometclient"
    docker cp "./abci/." "$container":/root/abci/ || { echo "Failed to copy abci files to $container"; exit 1; }
    docker cp "./cometclient/." "$container":/root/cometclient/ || { echo "Failed to copy main.py file to $container"; exit 1; }
    docker exec "$container" bash -c "cd /root/abci && /usr/local/go/bin/go clean -modcache && /usr/local/go/bin/go mod tidy && /usr/local/go/bin/go build -o /root/abci-app *.go"

    if   (( k >= 1  && k <= 17 )); then cluster="cluster1"
        elif (( k >= 18 && k <= 32 )); then cluster="cluster2"
        elif (( k >= 33 && k <= 42 )); then cluster="cluster3"
        elif (( (k >= 43 && k <= 50) || (k >= 57 && k <= 65) || k == 82 )); then cluster="cluster4"
        elif (( (k >= 66 && k <= 81) || (k >= 83 && k <= 95) )); then cluster="cluster5"
        elif (( (k >= 96 && k <= 126) || (k >= 128 && k <= 129) )); then cluster="cluster6"
        elif (( k == 127 || (k >= 130 && k <= 162) )); then cluster="cluster7"
        elif (( k >= 51 && k <= 56 )); then cluster="cluster8"
        else
            echo "ERROR: $container has no cluster mapping — skipping"
            continue
        fi

#    docker exec "$container" rm -f /root/.cometbft/config/genesis.json
    docker exec -d "$container" bash -c "cd /root/abci/clusterConfig && CLUSTER_NAME=$cluster nohup /root/abci-app > /root/logs/abci.log 2>&1"
#    docker cp "./${cluster}Config/genesis.json" "$container":/root/.cometbft/config/

#    nodeId=$(docker exec "$container" /root/go/bin/cometbft show-node-id)
#    docker exec "$container" curl -i -X POST -H "Content-Type: application/json" -d "{\"tags\":{\"rpc_addr\":\"$nodeId@$ip_address:26656\"}}" http://127.0.0.1:5555/updatetags
    docker exec -d "$container" bash -c "nohup /root/go/bin/cometbft node > /root/logs/cometbft.log 2>&1"
    sleep 2

    echo "[7] Verifying logs..."
    docker exec "$container" tail -n 20 /root/logs/abci.log
    docker exec "$container" tail -n 20 /root/logs/cometbft.log
    if [[ -n "${SELLER_NODES[$k]}" ]]; then
    echo "$container is a seller node — skipping"
    else
#      docker exec "$container" curl -i -X POST -H "Content-Type: application/json" -d "{\"tags\":{\"role\":\"buyer\"}}" http://127.0.0.1:5555/updatetags
      docker exec -d "$container" bash -c "cd /root/cometclient && nohup python3 tx_api.py > /root/logs/tx_api.log 2>&1 &"
    fi
    echo "✔ Done with $container"
  done
}

reset_cometbft
