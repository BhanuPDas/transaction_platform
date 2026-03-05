#!/bin/bash
# setup_k3s_liqo.sh
# Detects Liqo status and installs only where needed

# List of all container names
NODES=()
for i in $(seq 1 25); do
    NODES+=("clab-century-serf${i}")
done

for NODE in "${NODES[@]}"; do
    echo "--------------------------------------------------"
    echo "Checking Liqo state on node: $NODE"
    echo "--------------------------------------------------"

    # Run liqoctl info and capture output + error
    INFO_OUTPUT=$(sudo docker exec "$NODE" bash -c "liqoctl info" 2>&1)
    INFO_STATUS=$?

    # --- CASE 1: Healthy installation ---
    if [[ $INFO_STATUS -eq 0 && "$INFO_OUTPUT" == *"Liqo is healthy"* ]]; then
        echo "Liqo already healthy on $NODE. Skipping installation."
        echo
        continue
    fi

    # --- CASE 2: liqoctl missing ---
    if [[ "$INFO_OUTPUT" == *"executable file not found"* || "$INFO_OUTPUT" == *"command not found"* || "$INFO_OUTPUT" == *"Liqo is not installed"* ]]; then
        echo "liqoctl missing on $NODE → Installing..."
        INSTALL_REQUIRED=true
    else
        # --- CASE 3: liqoctl exists but not healthy / unknown error ---
        echo "liqoctl found but Liqo is NOT healthy on $NODE"
        echo "Manual inspection required"
        echo "Output was:"
        echo "$INFO_OUTPUT"
        echo
        continue
    fi

    # ----------------------------------------------------------------------
    # If we reach here, INSTALL_REQUIRED=true → proceed with installation
    # ----------------------------------------------------------------------
    echo "Proceeding with full installation on: $NODE"

    # Extract node number
    NODE_NUM=$(echo "$NODE" | grep -oP '(?<=serf)\d+')
    CLUSTER_ID="clab-serf-$NODE_NUM"

    # Get eth1 IP
    ETH1_IP=$(sudo docker exec "$NODE" bash -c "ip -4 addr show dev eth1 | grep -oP '(?<=inet\s)\d+(\.\d+){3}'")

    if [[ -z "$ETH1_IP" ]]; then
        echo "Could not detect eth1 IP for $NODE, skipping..."
        echo
        continue
    fi

    echo "Detected eth1 IP: $ETH1_IP"
    echo "Cluster ID: $CLUSTER_ID"

    # --- Update k3s.yaml ---
    echo "Updating k3s.yaml..."
    sudo docker exec "$NODE" bash -c "
        cp /etc/rancher/k3s/k3s.yaml /etc/rancher/k3s/k3s.yaml.bak &&
        sed -i 's/127\.0\.0\.1/$ETH1_IP/g' /etc/rancher/k3s/k3s.yaml
    "

    # --- Install liqoctl ---
    echo "Installing liqoctl..."
    sudo docker exec -i "$NODE" bash -c "
        curl --fail -LS 'https://github.com/liqotech/liqo/releases/download/v1.0.1/liqoctl-linux-amd64.tar.gz' | tar -xz &&
        install -o root -g root -m 0755 liqoctl /usr/local/bin/liqoctl
    "

    # --- Run liqoctl install ---
    echo "Running liqoctl install..."
    sudo docker exec -i "$NODE" bash -c "
        liqoctl install k3s --api-server-url https://$ETH1_IP:6443 --cluster-id $CLUSTER_ID
    "

    echo "Node $NODE setup complete."
    echo
done

echo "==============================="
echo "All nodes processed."
echo "==============================="
