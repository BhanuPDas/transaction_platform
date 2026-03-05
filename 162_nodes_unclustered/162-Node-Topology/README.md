# 162-Node Topology

Kubernetes cluster topology configurations for performance testing and workload modeling.

## Quick Start

 Navigate to the respective folder and check the **README.md** for detailed setup instructions and deployment steps.

---

## Topology Graph

<img width="1853" height="1077" alt="fig_network_topo_final" src="https://github.com/user-attachments/assets/143e907e-93f6-4e75-90ec-c8e6de468fa0" />

---

## Versions

### Extended Version
- Enhanced 162-node setup
- Additional monitoring capabilities
- Extended feature set for advanced testing

---

## Getting Started

1. Navigate to your preferred version directory
2. Read the version-specific README.md

---

### Prerequisites

- Docker & Containerlab installed
- Bash or Linux shell
- Git (for cloning and version control)

### Setup Steps

## How to Run (Extended version)

1. Run the orchestration script:
   ```bash
   ./orchestrate_serf.sh
   ```

   > It will take some time to pull the Docker images and start all pods.

2. If the pods are **not running** in seller nodes (Admission control and pricing pods), run on the seller nodes (change the loop based on seller order):
   ```bash
   for i in {1..162}; do echo "[serf$i] applying manifests..."; sudo docker exec -i clab-century-serf$i bash -lc 'export KUBECONFIG=/etc/rancher/k3s/k3s.yaml; for f in /tmp/qos-controller-daemonset.yaml /tmp/service-account.yaml /tmp/cluster-role.yaml /tmp/cluster-role-binding.yaml /tmp/deployment-scheduler.yaml /tmp/ram_price.yaml /tmp/storage_price.yaml /tmp/vcpu_price.yaml /tmp/vgpu_price.yaml; do if [ -s "$f" ]; then echo "  applying $f..."; k3s kubectl apply -f "$f" || echo "  [warn] failed $f"; fi; done'; done
   ```

3. To check if all pods are running on all nodes:
   ```bash
   for i in {1..162}; do echo -e "\n====== [serf$i] ======"; sudo docker exec -i clab-century-serf$i bash -lc 'export KUBECONFIG=/etc/rancher/k3s/k3s.yaml; k3s kubectl get pods -A -o wide --no-headers || echo "k3s not ready"'; done
   ```

---

## Running Sellers and Buyer (must have to wait untill all the pods run)

To start sellers, run from server:
```bash
./start_sellers.sh
```

to start buyer run from server:
```bash
./start_buyer
```
💡 **Alternative Option:** 
To run the buyer from inside each container for testing (inside the **buyer container**, path: `/opt/serfapp/`):
```bash
./config_buyer.sh
```
Then run the following command **inside the buyer container** (path: `/opt/serfapp/`).
If the file `service_discovery_v7.py` is not present in the container, copy it from this repository (path: `50node_topo/serfapp/`) into the container first.
```bash
python3 service_discovery_v7.py --geom-url http://172.20.20.17:4040/cluster-status --rtt-threshold-ms 12 --rpc-addr 127.0.0.1:7373 --timeout-s 8 --sort score_per_cpu --limit 30 --buyer-url http://127.0.0.1:8090/buyer --http-serve --http-host 0.0.0.0 --http-port 4041 --http-path /hilbert-output --loop --busy-secs 50
```
> ⚠️ **Note:** Update the `--geom-url` IP (`http://172.20.20.17:4040/cluster-status`) to match the IP of **serf1** (e.g., `172.20.20.XX`).

## Running Liqo

To install Liqo in the nodes execute the following command from your server:
```bash
./liqo_install/setup.sh
```

To start the Liqo API Server in the nodes:
```bash
./liqo_install/Workload_Offloading_API/setup_liqo_api.sh install
```
In order to check or destroy di liqo connections run the following script from your server: 162_nodes_unclustered/162-Node-Topology/extended version/liqo_install/liqo_disconnect.sh

## Author

Hamidreza Fathollahzadeh - Master's Student in Digital Transformation, Fachhochschule Dortmund
