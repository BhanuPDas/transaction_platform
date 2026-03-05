# `setup.sh`

This script automates the configuration of a multi-node K3s + Liqo environment inside a container-lab topology.

## What the script does
- Iterates over a list of container-lab nodes (default: `clab-century-serf1` → `clab-century-serf50`).
- Detects each node’s **eth1** IPv4 address.
- Updates the node’s `k3s.yaml` so the Kubernetes API server points to the correct IP.
- Installs `liqoctl` if not already installed.
- Runs `liqoctl install k3s` with a node-specific cluster ID.

## Important
Update the `NODES` range in the script to match the size of your topology:

```bash
for i in $(seq 1 50); do   # ← Change 50 to your number of Serf nodes
```

## How to run
1. Make the script executable:
   ```bash
   chmod +x setup.sh
   ```
2. Execute it:
   ```bash
   ./setup.sh
   ```

The script will walk through each node, update its K3s config, install Liqo, and complete the cluster setup.

