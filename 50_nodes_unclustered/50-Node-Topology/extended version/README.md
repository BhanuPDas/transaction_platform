# 50-Node K3s-Enabled Network Topology with 2 Routers (Extended Version)

This project provides a 50-node containerlab topology consisting of:

- 50 K3s serf nodes (serf1–serf50)
- 5 OVS switches
- 2 FRR routers (R1, R2) running OSPF
- A five-subnet Layer-3 routed design
- External IP and route configuration handled by deploy.sh

The topology is defined in: **extended-50node.yml**

---

The 50 nodes are grouped into five subnets. Each subnet is connected to one of the two routers. Routers run OSPF Area 0 over an interconnect link.

**Subnets:**
- 10.1.0.0/24 via R1 (switch_a, serf1–serf10),
- 10.2.0.0/24 via R1 (switch_b, serf11–serf20)
- 10.3.0.0/24 via R2 (switch_c, serf21–serf30)
- 10.4.0.0/24 via R2 (switch_d, serf31–serf40)
- 10.5.0.0/24 via R2 (switch_e, serf41–serf50)

---

## IP Addressing Table

### Routers

| Device | Interface | IP Address      | Connected To | Purpose |
|--------|-----------|-----------------|--------------|---------|
| R1     | eth1      | 192.168.0.1/30  | R2           | Router interconnect |
| R1     | eth2      | 10.1.0.254/24   | switch_a     | Gateway for serf1–10 |
| R1     | eth3      | 10.2.0.254/24   | switch_b     | Gateway for serf11–20 |
| R2     | eth1      | 192.168.0.2/30  | R1           | Router interconnect |
| R2     | eth2      | 10.3.0.254/24   | switch_c     | Gateway for serf21–30 |
| R2     | eth3      | 10.4.0.254/24   | switch_d     | Gateway for serf31–40 |
| R2     | eth4      | 10.5.0.254/24   | switch_e     | Gateway for serf41–50 |

### Client Subnet Allocation

| Switch    | Clients       | Subnet        | IP Range        | Gateway     | Router |
|-----------|---------------|---------------|-----------------|-------------|--------|
| switch_a  | serf1–serf10  | 10.1.0.0/24   | 10.1.0.1–10     | 10.1.0.254  | R1     |
| switch_b  | serf11–serf20 | 10.2.0.0/24   | 10.2.0.1–10     | 10.2.0.254  | R1     |
| switch_c  | serf21–serf30 | 10.3.0.0/24   | 10.3.0.1–10     | 10.3.0.254  | R2     |
| switch_d  | serf31–serf40 | 10.4.0.0/24   | 10.4.0.1–10     | 10.4.0.254  | R2     |
| switch_e  | serf41–serf50 | 10.5.0.0/24   | 10.5.0.1–10     | 10.5.0.254  | R2     |

---

## Detailed Client Mapping

### Switch A (via R1), BUYER nodes: serf7....serf10, VALIDATOR: serf10
```
serf1  = 10.1.0.1      serf2  = 10.1.0.2      serf3  = 10.1.0.3
serf4  = 10.1.0.4      serf5  = 10.1.0.5      serf6  = 10.1.0.6
serf7  = 10.1.0.7      serf8  = 10.1.0.8      serf9  = 10.1.0.9
serf10 = 10.1.0.10
```

### Switch B (via R1), BUYER nodes: serf17....serf20, VALIDATOR: serf20
```
serf11 = 10.2.0.1      serf12 = 10.2.0.2      serf13 = 10.2.0.3
serf14 = 10.2.0.4      serf15 = 10.2.0.5      serf16 = 10.2.0.6
serf17 = 10.2.0.7      serf18 = 10.2.0.8      serf19 = 10.2.0.9
serf20 = 10.2.0.10
```

### Switch C (via R2), BUYER nodes: serf27....serf30, VALIDATOR: serf30
```
serf21 = 10.3.0.1      serf22 = 10.3.0.2      serf23 = 10.3.0.3
serf24 = 10.3.0.4      serf25 = 10.3.0.5      serf26 = 10.3.0.6
serf27 = 10.3.0.7      serf28 = 10.3.0.8      serf29 = 10.3.0.9
serf30 = 10.3.0.10
```

### Switch D (via R2), BUYER nodes: serf37....serf40, VALIDATOR: serf40
```
serf31 = 10.4.0.1      serf32 = 10.4.0.2      serf33 = 10.4.0.3
serf34 = 10.4.0.4      serf35 = 10.4.0.5      serf36 = 10.4.0.6
serf37 = 10.4.0.7      serf38 = 10.4.0.8      serf39 = 10.4.0.9
serf40 = 10.4.0.10
```

### Switch E (via R2), BUYER nodes: serf47....serf50
```
serf41 = 10.5.0.1      serf42 = 10.5.0.2      serf43 = 10.5.0.3
serf44 = 10.5.0.4      serf45 = 10.5.0.5      serf46 = 10.5.0.6
serf47 = 10.5.0.7      serf48 = 10.5.0.8      serf49 = 10.5.0.9
serf50 = 10.5.0.10
```

---

## Routing

- **Protocol**: OSPF (Area 0)
- **Router-to-Router link**: 192.168.0.0/30
- **OSPF Neighbors**: R1 ↔ R2
- **Client Routes**: 10.0.0.0/8 via subnet gateway (eth1)
- **Management access**: Default route via eth0 for all nodes

---

## Files Included

```
.
├── extended-50node.yml          # Main topology definition
├── daemons                      # FRR daemon activation file
├── r1.conf                      # Router R1 OSPF configuration
├── r2.conf                      # Router R2 OSPF configuration
├── deploy.sh                    # Automated deployment and IP assignment
├── full-ping-matrix.sh          # Complete connectivity test script
└── README.md                    # This file
```

---

## Prerequisites

- Docker installed
- Containerlab installed
- Open vSwitch installed

**Check versions:**
```bash
sudo clab version
sudo ovs-vsctl show
docker --version
```

---

## Quick Start

**Deploy the full topology:**
```bash
./orchestrate_serf.sh
```

**Run complete connectivity validation:**
```bash
./full-ping-matrix.sh
```

**View topology graph:**
```bash
sudo clab graph -t extended-50node.yml
# Open http://localhost:50080 in browser
```

---

## Manual Deployment

```bash
# Deploy topology
sudo clab deploy -t extended-50node.yml

# After deployment, IP assignment is handled by deploy.sh
# Check OSPF status
docker exec clab-extended50-R1 vtysh -c "show ip ospf neighbor"
docker exec clab-extended50-R1 vtysh -c "show ip route ospf"

# Test connectivity
docker exec clab-extended50-serf1 ping -c 3 10.5.0.10
```

---

## Cleanup

```bash
sudo clab destroy -t extended-50node.yml --cleanup
```

---

## Troubleshooting

### OSPF Not Working
```bash
# Check OSPF neighbors
docker exec clab-extended50-R1 vtysh -c "show ip ospf neighbor"
# Should show R2 as neighbor in Full/DR or Full/Backup state
```

### Clients Can't Ping
```bash
# Check client IP
docker exec clab-extended50-serf1 ip addr show eth1

# Check routes
docker exec clab-extended50-serf1 ip route
# Should have: 10.0.0.0/8 via 10.1.0.254 dev eth1
```

### Router Not Forwarding
```bash
# Check IP forwarding enabled
docker exec clab-extended50-R1 sysctl net.ipv4.ip_forward
# Should return: net.ipv4.ip_forward = 1

# Check FRR is running
docker exec clab-extended50-R1 ps aux | grep ospfd
```

---

## K3s Node Configuration

Each serf node runs a K3s server instance with:
- Custom initialization script
- Disabled default services (traefik, servicelb, etc.)
- Relaxed cgroup settings for containerlab compatibility
- Pre-cached container images
- Custom QoS controllers and schedulers

**IP assignment is intentionally done externally** (via deploy.sh) to avoid race conditions during K3s startup.

---

## Performance Notes

- **K3s containers**: ~1-2GB each, 30-60 seconds to fully initialize
- **Full deployment**: ~5-10 minutes with K3s images
- **Alpine alternative**: Use Alpine images for faster testing (~30 seconds total)

---

## Testing Results

**Expected connectivity:**
- ✓ All 50 nodes can ping each other
- ✓ OSPF convergence < 30 seconds
- ✓ Ping latency within lab: < 1ms
- ✓ Ping latency across routers: 1-2ms
- ✓ Internet access maintained via eth0

---

## Use Cases

- Multi-cluster Kubernetes simulations
- OSPF behavior analysis
- Network protocol testing
- Large-scale connectivity testing
- Distributed systems research
- Container orchestration at scale

---

## Important Notes

- Each serf node runs a K3s server instance with a custom initialization script
- IP assignment is intentionally not done inside the YAML to avoid race conditions
- The `deploy.sh` script configures all serf IPs and routes before K3s fully initializes
- OSPF dynamically learns all five subnets via R1 and R2
- Management network (eth0) remains accessible for all nodes


---

**Updated**: December 2025  
**Topology Name**: extended50  
**Total Nodes**: 57 (2 routers + 5 switches + 50 K3s serf nodes)
