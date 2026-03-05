#!/bin/bash
# setup_liqo_api.sh
# This script installs, resets, or stops the liqo_api.py Flask service on all k3s containers.

# Usage:
#   ./setup_liqo_api.sh install
#   ./setup_liqo_api.sh reset
#   ./setup_liqo_api.sh stop

ACTION=$1

if [[ -z "$ACTION" ]]; then
    echo "No action specified."
    echo "Usage: $0 <install|reset|stop>"
    exit 1
fi

# List of all container names
NODES=()
for i in $(seq 1 25); do
    NODES+=("clab-century-serf${i}")
done

# Path to local liqo_api.py
API_FILE="liqo_api.py"

# Check if the file exists (only for install/reset)
if [[ "$ACTION" != "stop" && ! -f "$API_FILE" ]]; then
    echo "$API_FILE not found in current directory"
    exit 1
fi

for NODE in "${NODES[@]}"; do
    echo "---------------------------"
    echo "Working on node: $NODE"
    echo "---------------------------"

    if [[ "$ACTION" == "install" ]]; then
        echo "Installing Python + dependencies..."
        sudo docker exec -it "$NODE" bash -c "
            apt-get update -y &&
            apt-get install -y python3 python3-pip &&
            pip3 install flask pyyaml requests redis
        "
    fi

    if [[ "$ACTION" == "install" || "$ACTION" == "reset" ]]; then
        echo "Copying liqo_api.py..."
        sudo docker cp "$API_FILE" "$NODE":/root/liqo_api.py
    fi

    echo "Stopping any running liqo_api.py processes..."
    sudo docker exec -it "$NODE" bash -c "
        pkill -f liqo_api.py || true
    "

    if [[ "$ACTION" == "install" || "$ACTION" == "reset" ]]; then
        echo "Starting Flask server..."
        sudo docker exec -d "$NODE" bash -c "
            nohup python3 /root/liqo_api.py > /root/liqo_api.log 2>&1 &
        "
        echo "Node $NODE ${ACTION} complete."
    elif [[ "$ACTION" == "stop" ]]; then
        echo "Flask service stopped on $NODE."
    fi

    echo
done

echo "All nodes processed for action: $ACTION"
if [[ "$ACTION" != "stop" ]]; then
    echo "You can verify with: curl http://<node_ip>:5000/status"
fi
