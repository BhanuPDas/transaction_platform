# 162-Node K3s Extended Topology

Complete Containerlab topology with 162 K3s server nodes, 27 OSPF routers, and 37 OVS switches for large-scale Kubernetes orchestration testing.

---

## Overview

- **162 K3s server nodes** running as independent clusters with full controllers
- **27 FRR routers** configured with OSPF (Area 0)
- **37 OVS switches** for Layer 2 connectivity
- **83 subnetworks** (10.0.1.0/24 through 10.0.83.0/24)
- **Full K3s features**: QoS controllers, custom schedulers, and resource pricing models

---

## Architecture

### Network Topology

The nodes are marked in the topology diagram:
- **Green**: Switches (OVS bridges)
- **Yellow**: Routers (FRR with OSPF)
- **White**: K3s Serf Nodes

<img width="1853" height="1077" alt="fig_network_topo_final" src="https://github.com/user-attachments/assets/143e907e-93f6-4e75-90ec-c8e6de468fa0" />

### Network Segments

| Segment | Subnet | Gateway | Router | Switch | Nodes |
|---------|--------|---------|---------|---------|-------------|
| **net_1** | 10.0.1.0/24 | 10.0.1.1 | R1 | S1-S4 | serf1-serf14 |
| **net_2** | 10.0.2.0/24 | 10.0.2.1 | R1 | S5 | serf15 |
| **net_3** | 10.0.3.0/24 | 10.0.3.1 | R1 | - | serf16 |
| ... | ... | ... | ... | ... | ... |
| **net_83** | 10.0.83.0/24 | 10.0.83.1 | R27 | S37 | serf162 |

> **Note:** First IP (.1) is the router gateway. Nodes start at .10 and increment (.11, .12, etc.)

---

## Components

| Node | Kind | Version | Image |
|------|------|---------|-------|
| Router | linux | 10.2.1 | quay.io/frrouting/frr:10.2.1 |
| Switch | ovs-bridge | 3.3.0 | - |
| K3s Serf Node | linux | K3s v1.28+ | abdullahmuzlim279/k3s-serf-node:warmcache-test |

### K3s Node Features

Each serf node includes:
- **K3s Server** with disabled default services (traefik, servicelb, metrics-server)
- **QoS Controller DaemonSet** for quality-of-service management
- **Custom Scheduler** with resource-aware pod placement
- **Price Models** (RAM, vCPU, vGPU, Storage) for cost simulation
- **Relaxed cgroup settings** for containerlab compatibility
- **Pre-cached container images** for faster initialization

---

## Configuration Files

| Name | Purpose |
|------|---------|
| `extended-162node.yml` | Main topology configuration with K3s nodes |
| `ip-mapping.txt` | IP address mapping for all 162 nodes |
| `scripts/init.sh` | Network configuration script (runs inside containers) |
| `scripts/create_ovs_bridges.sh` | Create 37 Open vSwitch bridges |
| `router1-27/` | FRR router configurations (daemons + frr.conf) |

---

## Prerequisites

### Required Software
- Docker installed and running
- Containerlab 0.48.0+ ([Installation Guide](https://containerlab.dev/install/))
- Open vSwitch 3.0+ ([Installation Guide](https://www.openvswitch.org/))

### Check Versions
```bash
docker --version
sudo clab version
sudo ovs-vsctl --version
```

### Resource Requirements

**Minimum:**
- RAM: 180GB
- CPU: 32 cores
- Disk: 200GB free

**Recommended:**
- RAM: 240GB+
- CPU: 64 cores
- Disk: 500GB free
- Network: 10Gbps for faster image pulls

---

## Quick Start

### Step 1: Create OVS Bridges
```bash
# Create all 37 switches
sudo ./scripts/create_ovs_bridges.sh

# Verify
sudo ovs-vsctl list-br | wc -l
# Expected output: 37
```

### Step 2: Deploy Topology
```bash
sudo clab deploy --reconfigure -t extended-162node.yml
```

**Expected Timeline:**
- **0-5 min**: Containers starting (242 total: 162 serfs + 27 routers + 37 switches + overhead)
- **5-10 min**: IP configuration via init.sh, K3s servers starting
- **10-20 min**: K3s importing cached images, deploying controllers
- **20+ min**: All 162 K3s clusters fully operational

### Step 4: Monitor Deployment

**In another terminal:**
```bash
# Watch container count
watch -n 10 'docker ps | grep -c Running'

# Watch specific node initialization
docker logs clab-nebula-extended-serf1 --tail 20 --follow
```

**Expected container count progression:**
```
Minute 1:  ~50 containers
Minute 3:  ~200 containers
Minute 5:  ~242 containers (all running)
```

---

## Verification

### After 5 Minutes: Check Networking

```bash
# Verify OSPF on routers
docker exec clab-nebula-extended-router1 vtysh -c "show ip ospf neighbor"
# Expected: Full/DR or Full/Backup adjacency with neighbors

# Check serf1 IP configuration
docker exec clab-nebula-extended-serf1 ip addr show eth1
# Expected: 10.0.1.10/24

# Test cross-subnet connectivity
docker exec clab-nebula-extended-serf1 ping -c 3 10.0.50.10
docker exec clab-nebula-extended-serf15 ping -c 3 10.0.83.10
```

### After 20 Minutes: Check K3s Clusters

```bash
# Check K3s on serf1
docker exec clab-nebula-extended-serf1 k3s kubectl get nodes
# Expected: serf1   Ready   control-plane,master

# Check controllers deployed
docker exec clab-nebula-extended-serf1 k3s kubectl get pods -A
# Expected: Multiple pods Running (qos-controller, scheduler, etc.)

# Quick connectivity matrix
for i in 1 25 50 75 100 125 150 162; do
  echo -n "Testing serf${i}... "
  docker exec clab-nebula-extended-serf${i} ping -c 2 10.0.1.10 >/dev/null 2>&1 && \
    echo "✓ OK" || echo "✗ FAIL"
done
```

### Check Specific K3s Features

```bash
# Verify QoS controller
docker exec clab-nebula-extended-serf1 k3s kubectl get daemonsets -A | grep qos

# Verify custom scheduler
docker exec clab-nebula-extended-serf1 k3s kubectl get deployment -A | grep scheduler

# Check price models (ConfigMaps)
docker exec clab-nebula-extended-serf1 k3s kubectl get configmap -A | grep price
```

---

## Expected Resource Usage

### Per Node (Steady State):
- CPU: 0.1-0.3 cores
- RAM: ~1GB
- Disk: ~500MB

### Total (162 nodes):
- CPU: 20-50 cores active
- RAM: 160-200GB
- Disk: ~100GB
- Network: Minimal after initialization

---

## Cleanup

### Destroy Topology
```bash
sudo clab destroy -t extended-162node.yml --cleanup
```

### Remove OVS Bridges (Optional)
```bash
for i in {1..37}; do
    sudo ovs-vsctl del-br switch$i 2>/dev/null || true
done
```

---

## Use Cases

- Multi-cluster Kubernetes orchestration testing
- Large-scale K8s scheduler algorithm development
- OSPF routing protocol analysis at scale
- Resource consumption modeling with price simulation
- QoS controller testing across distributed clusters
- Container orchestration performance benchmarking

---

## IP mapping

| Rete   | CIDR           | Host     | IP Host           | Gateway      |
|--------|----------------|----------|-------------------|--------------|
| net_1  | 10.0.1.0/24    | serf1    | 10.0.1.10/24      | 10.0.1.1    |
| net_1  | 10.0.1.0/24    | serf2    | 10.0.1.11/24      | 10.0.1.1    |
| net_1  | 10.0.1.0/24    | serf3    | 10.0.1.12/24      | 10.0.1.1    |
| net_1  | 10.0.1.0/24    | serf4    | 10.0.1.13/24      | 10.0.1.1    |
| net_1  | 10.0.1.0/24    | serf5    | 10.0.1.14/24      | 10.0.1.1    |
| net_1  | 10.0.1.0/24    | serf6    | 10.0.1.15/24      | 10.0.1.1    |
| net_1  | 10.0.1.0/24    | serf7    | 10.0.1.16/24      | 10.0.1.1    |
| net_1  | 10.0.1.0/24    | serf8    | 10.0.1.17/24      | 10.0.1.1    |
| net_1  | 10.0.1.0/24    | serf9    | 10.0.1.18/24      | 10.0.1.1    |
| net_1  | 10.0.1.0/24    | serf10   | 10.0.1.19/24      | 10.0.1.1    |
| net_1  | 10.0.1.0/24    | serf11   | 10.0.1.20/24      | 10.0.1.1    |
| net_1  | 10.0.1.0/24    | serf12   | 10.0.1.21/24      | 10.0.1.1    |
| net_1  | 10.0.1.0/24    | serf13   | 10.0.1.22/24      | 10.0.1.1    |
| net_1  | 10.0.1.0/24    | serf14   | 10.0.1.23/24      | 10.0.1.1    |
| net_2  | 10.0.2.0/24    | serf15   | 10.0.2.10/24      | 10.0.2.1    |
| net_3  | 10.0.3.0/24    | serf16   | 10.0.3.10/24      | 10.0.3.1    |
| net_4  | 10.0.4.0/24    | serf17   | 10.0.4.10/24      | 10.0.4.1    |
| net_5  | 10.0.5.0/24    | serf18   | 10.0.5.10/24      | 10.0.5.1    |
| net_6  | 10.0.6.0/24    | serf19   | 10.0.6.10/24      | 10.0.6.1    |
| net_7  | 10.0.7.0/24    | serf20   | 10.0.7.10/24      | 10.0.7.1    |
| net_7  | 10.0.7.0/24    | serf21   | 10.0.7.11/24      | 10.0.7.1    |
| net_8  | 10.0.8.0/24    | serf22   | 10.0.8.10/24      | 10.0.8.1    |
| net_8  | 10.0.8.0/24    | serf23   | 10.0.8.11/24      | 10.0.8.1    |
| net_8  | 10.0.8.0/24    | serf24   | 10.0.8.12/24      | 10.0.8.1    |
| net_8  | 10.0.8.0/24    | serf25   | 10.0.8.13/24      | 10.0.8.1    |
| net_9  | 10.0.9.0/24    | serf26   | 10.0.9.10/24      | 10.0.9.1    |
| net_10 | 10.0.10.0/24   | serf27   | 10.0.10.10/24     | 10.0.10.1   |
| net_10 | 10.0.10.0/24   | serf28   | 10.0.10.11/24     | 10.0.10.1   |
| net_10 | 10.0.10.0/24   | serf29   | 10.0.10.12/24     | 10.0.10.1   |
| net_11 | 10.0.11.0/24   | serf30   | 10.0.11.10/24     | 10.0.11.1   |
| net_12 | 10.0.12.0/24   | serf31   | 10.0.12.10/24     | 10.0.12.1   |
| net_13 | 10.0.13.0/24   | serf32   | 10.0.13.10/24     | 10.0.13.1   |
| net_14 | 10.0.14.0/24   | serf33   | 10.0.14.10/24     | 10.0.14.1   |
| net_14 | 10.0.14.0/24   | serf34   | 10.0.14.11/24     | 10.0.14.1   |
| net_15 | 10.0.15.0/24   | serf35   | 10.0.15.10/24     | 10.0.15.1   |
| net_15 | 10.0.15.0/24   | serf36   | 10.0.15.11/24     | 10.0.15.1   |
| net_15 | 10.0.15.0/24   | serf37   | 10.0.15.12/24     | 10.0.15.1   |
| net_15 | 10.0.15.0/24   | serf38   | 10.0.15.13/24     | 10.0.15.1   |
| net_15 | 10.0.15.0/24   | serf39   | 10.0.15.14/24     | 10.0.15.1   |
| net_15 | 10.0.15.0/24   | serf40   | 10.0.15.15/24     | 10.0.15.1   |
| net_15 | 10.0.15.0/24   | serf41   | 10.0.15.16/24     | 10.0.15.1   |
| net_15 | 10.0.15.0/24   | serf42   | 10.0.15.17/24     | 10.0.15.1   |
| net_16 | 10.0.16.0/24   | serf43   | 10.0.16.10/24     | 10.0.16.1   |
| net_16 | 10.0.16.0/24   | serf44   | 10.0.16.11/24     | 10.0.16.1   |
| net_16 | 10.0.16.0/24   | serf45   | 10.0.16.12/24     | 10.0.16.1   |
| net_17 | 10.0.17.0/24   | serf46   | 10.0.17.10/24     | 10.0.17.1   |
| net_18 | 10.0.18.0/24   | serf47   | 10.0.18.10/24     | 10.0.18.1   |
| net_19 | 10.0.19.0/24   | serf48   | 10.0.19.10/24     | 10.0.19.1   |
| net_20 | 10.0.20.0/24   | serf49   | 10.0.20.10/24     | 10.0.20.1   |
| net_21 | 10.0.21.0/24   | serf50   | 10.0.21.10/24     | 10.0.21.1   |
| net_22 | 10.0.22.0/24   | serf51   | 10.0.22.10/24     | 10.0.22.1   |
| net_23 | 10.0.23.0/24   | serf52   | 10.0.23.10/24     | 10.0.23.1   |
| net_24 | 10.0.24.0/24   | serf53   | 10.0.24.10/24     | 10.0.24.1   |
| net_25 | 10.0.25.0/24   | serf54   | 10.0.25.10/24     | 10.0.25.1   |
| net_26 | 10.0.26.0/24   | serf55   | 10.0.26.10/24     | 10.0.26.1   |
| net_27 | 10.0.27.0/24   | serf56   | 10.0.27.10/24     | 10.0.27.1   |
| net_28 | 10.0.28.0/24   | serf57   | 10.0.28.10/24     | 10.0.28.1   |
| net_29 | 10.0.29.0/24   | serf58   | 10.0.29.10/24     | 10.0.29.1   |
| net_30 | 10.0.30.0/24   | serf59   | 10.0.30.10/24     | 10.0.30.1   |
| net_31 | 10.0.31.0/24   | serf60   | 10.0.31.10/24     | 10.0.31.1   |
| net_32 | 10.0.32.0/24   | serf61   | 10.0.32.10/24     | 10.0.32.1   |
| net_33 | 10.0.33.0/24   | serf62   | 10.0.33.10/24     | 10.0.33.1   |
| net_34 | 10.0.34.0/24   | serf63   | 10.0.34.10/24     | 10.0.34.1   |
| net_35 | 10.0.35.0/24   | serf64   | 10.0.35.10/24     | 10.0.35.1   |
| net_36 | 10.0.36.0/24   | serf65   | 10.0.36.10/24     | 10.0.36.1   |
| net_37 | 10.0.37.0/24   | serf66   | 10.0.37.10/24     | 10.0.37.1   |
| net_37 | 10.0.37.0/24   | serf67   | 10.0.37.11/24     | 10.0.37.1   |
| net_37 | 10.0.37.0/24   | serf68   | 10.0.37.12/24     | 10.0.37.1   |
| net_38 | 10.0.38.0/24   | serf69   | 10.0.38.10/24     | 10.0.38.1   |
| net_38 | 10.0.38.0/24   | serf70   | 10.0.38.11/24     | 10.0.38.1   |
| net_38 | 10.0.38.0/24   | serf71   | 10.0.38.12/24     | 10.0.38.1   |
| net_38 | 10.0.38.0/24   | serf72   | 10.0.38.13/24     | 10.0.38.1   |
| net_38 | 10.0.38.0/24   | serf73   | 10.0.38.14/24     | 10.0.38.1   |
| net_38 | 10.0.38.0/24   | serf74   | 10.0.38.15/24     | 10.0.38.1   |
| net_38 | 10.0.38.0/24   | serf75   | 10.0.38.16/24     | 10.0.38.1   |
| net_38 | 10.0.38.0/24   | serf76   | 10.0.38.17/24     | 10.0.38.1   |
| net_38 | 10.0.38.0/24   | serf77   | 10.0.38.18/24     | 10.0.38.1   |
| net_38 | 10.0.38.0/24   | serf78   | 10.0.38.19/24     | 10.0.38.1   |
| net_38 | 10.0.38.0/24   | serf79   | 10.0.38.20/24     | 10.0.38.1   |
| net_39 | 10.0.39.0/24   | serf80   | 10.0.39.10/24     | 10.0.39.1   |
| net_40 | 10.0.40.0/24   | serf81   | 10.0.40.10/24     | 10.0.40.1   |
| net_41 | 10.0.41.0/24   | serf82   | 10.0.41.10/24     | 10.0.41.1   |
| net_42 | 10.0.42.0/24   | serf83   | 10.0.42.10/24     | 10.0.42.1   |
| net_42 | 10.0.42.0/24   | serf84   | 10.0.42.11/24     | 10.0.42.1   |
| net_42 | 10.0.42.0/24   | serf85   | 10.0.42.12/24     | 10.0.42.1   |
| net_42 | 10.0.42.0/24   | serf86   | 10.0.42.13/24     | 10.0.42.1   |
| net_42 | 10.0.42.0/24   | serf87   | 10.0.42.14/24     | 10.0.42.1   |
| net_42 | 10.0.42.0/24   | serf88   | 10.0.42.15/24     | 10.0.42.1   |
| net_42 | 10.0.42.0/24   | serf89   | 10.0.42.16/24     | 10.0.42.1   |
| net_43 | 10.0.43.0/24   | serf90   | 10.0.43.10/24     | 10.0.43.1   |
| net_44 | 10.0.44.0/24   | serf91   | 10.0.44.10/24     | 10.0.44.1   |
| net_45 | 10.0.45.0/24   | serf92   | 10.0.45.10/24     | 10.0.45.1   |
| net_46 | 10.0.46.0/24   | serf93   | 10.0.46.10/24     | 10.0.46.1   |
| net_47 | 10.0.47.0/24   | serf94   | 10.0.47.10/24     | 10.0.47.1   |
| net_48 | 10.0.48.0/24   | serf95   | 10.0.48.10/24     | 10.0.48.1   |
| net_49 | 10.0.49.0/24   | serf96   | 10.0.49.10/24     | 10.0.49.1   |
| net_49 | 10.0.49.0/24   | serf97   | 10.0.49.11/24     | 10.0.49.1   |
| net_49 | 10.0.49.0/24   | serf98   | 10.0.49.12/24     | 10.0.49.1   |
| net_50 | 10.0.50.0/24   | serf99   | 10.0.50.10/24     | 10.0.50.1   |
| net_51 | 10.0.51.0/24   | serf100  | 10.0.51.10/24     | 10.0.51.1   |
| net_52 | 10.0.52.0/24   | serf101  | 10.0.52.10/24     | 10.0.52.1   |
| net_53 | 10.0.53.0/24   | serf102  | 10.0.53.10/24     | 10.0.53.1   |
| net_54 | 10.0.54.0/24   | serf103  | 10.0.54.10/24     | 10.0.54.1   |
| net_55 | 10.0.55.0/24   | serf104  | 10.0.55.10/24     | 10.0.55.1   |
| net_56 | 10.0.56.0/24   | serf105  | 10.0.56.10/24     | 10.0.56.1   |
| net_57 | 10.0.57.0/24   | serf106  | 10.0.57.10/24     | 10.0.57.1   |
| net_58 | 10.0.58.0/24   | serf107  | 10.0.58.10/24     | 10.0.58.1   |
| net_59 | 10.0.59.0/24   | serf108  | 10.0.59.10/24     | 10.0.59.1   |
| net_60 | 10.0.60.0/24   | serf109  | 10.0.60.10/24     | 10.0.60.1   |
| net_61 | 10.0.61.0/24   | serf110  | 10.0.61.10/24     | 10.0.61.1   |
| net_62 | 10.0.62.0/24   | serf111  | 10.0.62.10/24     | 10.0.62.1   |
| net_63 | 10.0.63.0/24   | serf112  | 10.0.63.10/24     | 10.0.63.1   |
| net_63 | 10.0.63.0/24   | serf113  | 10.0.63.11/24     | 10.0.63.1   |
| net_63 | 10.0.63.0/24   | serf114  | 10.0.63.12/24     | 10.0.63.1   |
| net_64 | 10.0.64.0/24   | serf115  | 10.0.64.10/24     | 10.0.64.1   |
| net_64 | 10.0.64.0/24   | serf116  | 10.0.64.11/24     | 10.0.64.1   |
| net_65 | 10.0.65.0/24   | serf117  | 10.0.65.10/24     | 10.0.65.1   |
| net_65 | 10.0.65.0/24   | serf118  | 10.0.65.11/24     | 10.0.65.1   |
| net_65 | 10.0.65.0/24   | serf119  | 10.0.65.12/24     | 10.0.65.1   |
| net_65 | 10.0.65.0/24   | serf120  | 10.0.65.13/24     | 10.0.65.1   |
| net_66 | 10.0.66.0/24   | serf121  | 10.0.66.10/24     | 10.0.66.1   |
| net_67 | 10.0.67.0/24   | serf122  | 10.0.67.10/24     | 10.0.67.1   |
| net_68 | 10.0.68.0/24   | serf123  | 10.0.68.10/24     | 10.0.68.1   |
| net_69 | 10.0.69.0/24   | serf124  | 10.0.69.10/24     | 10.0.69.1   |
| net_70 | 10.0.70.0/24   | serf125  | 10.0.70.10/24     | 10.0.70.1   |
| net_71 | 10.0.71.0/24   | serf126  | 10.0.71.10/24     | 10.0.71.1   |
| net_72 | 10.0.72.0/24   | serf127  | 10.0.72.10/24     | 10.0.72.1   |
| net_73 | 10.0.73.0/24   | serf128  | 10.0.73.10/24     | 10.0.73.1   |
| net_74 | 10.0.74.0/24   | serf129  | 10.0.74.10/24     | 10.0.74.1   |
| net_75 | 10.0.75.0/24   | serf130  | 10.0.75.10/24     | 10.0.75.1   |
| net_75 | 10.0.75.0/24   | serf131  | 10.0.75.11/24     | 10.0.75.1   |
| net_75 | 10.0.75.0/24   | serf132  | 10.0.75.12/24     | 10.0.75.1   |
| net_75 | 10.0.75.0/24   | serf133  | 10.0.75.13/24     | 10.0.75.1   |
| net_75 | 10.0.75.0/24   | serf134  | 10.0.75.14/24     | 10.0.75.1   |
| net_75 | 10.0.75.0/24   | serf135  | 10.0.75.15/24     | 10.0.75.1   |
| net_75 | 10.0.75.0/24   | serf136  | 10.0.75.16/24     | 10.0.75.1   |
| net_75 | 10.0.75.0/24   | serf137  | 10.0.75.17/24     | 10.0.75.1   |
| net_75 | 10.0.75.0/24   | serf138  | 10.0.75.18/24     | 10.0.75.1   |
| net_75 | 10.0.75.0/24   | serf139  | 10.0.75.19/24     | 10.0.75.1   |
| net_75 | 10.0.75.0/24   | serf140  | 10.0.75.20/24     | 10.0.75.1   |
| net_75 | 10.0.75.0/24   | serf141  | 10.0.75.21/24     | 10.0.75.1   |
| net_76 | 10.0.76.0/24   | serf142  | 10.0.76.10/24     | 10.0.76.1   |
| net_76 | 10.0.76.0/24   | serf143  | 10.0.76.11/24     | 10.0.76.1   |
| net_76 | 10.0.76.0/24   | serf144  | 10.0.76.12/24     | 10.0.76.1   |
| net_76 | 10.0.76.0/24   | serf145  | 10.0.76.13/24     | 10.0.76.1   |
| net_76 | 10.0.76.0/24   | serf146  | 10.0.76.14/24     | 10.0.76.1   |
| net_77 | 10.0.77.0/24   | serf147  | 10.0.77.10/24     | 10.0.77.1   |
| net_77 | 10.0.77.0/24   | serf148  | 10.0.77.11/24     | 10.0.77.1   |
| net_77 | 10.0.77.0/24   | serf149  | 10.0.77.12/24     | 10.0.77.1   |
| net_77 | 10.0.77.0/24   | serf150  | 10.0.77.13/24     | 10.0.77.1   |
| net_77 | 10.0.77.0/24   | serf151  | 10.0.77.14/24     | 10.0.77.1   |
| net_77 | 10.0.77.0/24   | serf152  | 10.0.77.15/24     | 10.0.77.1   |
| net_77 | 10.0.77.0/24   | serf153  | 10.0.77.16/24     | 10.0.77.1   |
| net_77 | 10.0.77.0/24   | serf154  | 10.0.77.17/24     | 10.0.77.1   |
| net_77 | 10.0.77.0/24   | serf155  | 10.0.77.18/24     | 10.0.77.1   |
| net_77 | 10.0.77.0/24   | serf156  | 10.0.77.19/24     | 10.0.77.1   |
| net_78 | 10.0.78.0/24   | serf157  | 10.0.78.10/24     | 10.0.78.1   |
| net_79 | 10.0.79.0/24   | serf158  | 10.0.79.10/24     | 10.0.79.1   |
| net_80 | 10.0.80.0/24   | serf159  | 10.0.80.10/24     | 10.0.80.1   |
| net_81 | 10.0.81.0/24   | serf160  | 10.0.81.10/24     | 10.0.81.1   |
| net_82 | 10.0.82.0/24   | serf161  | 10.0.82.10/24     | 10.0.82.1   |
| net_83 | 10.0.83.0/24   | serf162  | 10.0.83.10/24     | 10.0.83.1   |

---


## Support & Documentation

- **Original Topology**: [hlnanayakkara/162Topology](https://github.com/hlnanayakkara/162Topology)
- **50-Node Reference**: [Hamidhrf/50-Node-Topology](https://github.com/Hamidhrf/50-Node-Topology)
- **Containerlab Docs**: https://containerlab.dev
- **K3s Documentation**: https://docs.k3s.io

---

## Credits

- **Base Topology**: hlnanayakkara/162Topology
- **K3s Configuration**: Based on 50-Node-Topology extended version
- **Extended Version**: Hamidreza Fathollahzadeh (FH Dortmund)

---

**Last Updated**: December 2025  
**Topology Name**: nebula-extended  
**Total Nodes**: 242 (162 K3s serfs + 27 routers + 37 switches + overhead)  
