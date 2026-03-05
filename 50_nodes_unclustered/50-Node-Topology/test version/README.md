# 50-Node Network Topology with 2 Routers

Complete containerlab topology with 50 Alpine Linux clients connected via 2 OSPF routers and 5 OVS switches.

## Architecture


## IP Addressing Table

### Routers

| Device | Interface | IP Address      | Connected To | Purpose |
|--------|-----------|-----------------|--------------|---------|
| R1     | eth1      | 192.168.0.1/30  | R2           | Router interconnect |
| R1     | eth2      | 10.1.0.254/24   | switch_a     | Gateway for C1-10 |
| R1     | eth3      | 10.2.0.254/24   | switch_b     | Gateway for C11-20 |
| R2     | eth1      | 192.168.0.2/30  | R1           | Router interconnect |
| R2     | eth2      | 10.3.0.254/24   | switch_c     | Gateway for C21-30 |
| R2     | eth3      | 10.4.0.254/24   | switch_d     | Gateway for C31-40 |
| R2     | eth4      | 10.5.0.254/24   | switch_e     | Gateway for C41-50 |

### Clients

| Switch    | Clients | Subnet        | IP Range        | Gateway     | Router |
|-----------|---------|---------------|-----------------|-------------|--------|
| switch_a  | C1-C10  | 10.1.0.0/24   | 10.1.0.1-10     | 10.1.0.254  | R1     |
| switch_b  | C11-C20 | 10.2.0.0/24   | 10.2.0.1-10     | 10.2.0.254  | R1     |
| switch_c  | C21-C30 | 10.3.0.0/24   | 10.3.0.1-10     | 10.3.0.254  | R2     |
| switch_d  | C31-C40 | 10.4.0.0/24   | 10.4.0.1-10     | 10.4.0.254  | R2     |
| switch_e  | C41-C50 | 10.5.0.0/24   | 10.5.0.1-10     | 10.5.0.254  | R2     |

### Detailed Client Mapping
```
Switch A (via R1):
C1  = 10.1.0.1     C2  = 10.1.0.2     C3  = 10.1.0.3     C4  = 10.1.0.4     C5  = 10.1.0.5
C6  = 10.1.0.6     C7  = 10.1.0.7     C8  = 10.1.0.8     C9  = 10.1.0.9     C10 = 10.1.0.10

Switch B (via R1):
C11 = 10.2.0.1     C12 = 10.2.0.2     C13 = 10.2.0.3     C14 = 10.2.0.4     C15 = 10.2.0.5
C16 = 10.2.0.6     C17 = 10.2.0.7     C18 = 10.2.0.8     C19 = 10.2.0.9     C20 = 10.2.0.10

Switch C (via R2):
C21 = 10.3.0.1     C22 = 10.3.0.2     C23 = 10.3.0.3     C24 = 10.3.0.4     C25 = 10.3.0.5
C26 = 10.3.0.6     C27 = 10.3.0.7     C28 = 10.3.0.8     C29 = 10.3.0.9     C30 = 10.3.0.10

Switch D (via R2):
C31 = 10.4.0.1     C32 = 10.4.0.2     C33 = 10.4.0.3     C34 = 10.4.0.4     C35 = 10.4.0.5
C36 = 10.4.0.6     C37 = 10.4.0.7     C38 = 10.4.0.8     C39 = 10.4.0.9     C40 = 10.4.0.10

Switch E (via R2):
C41 = 10.5.0.1     C42 = 10.5.0.2     C43 = 10.5.0.3     C44 = 10.5.0.4     C45 = 10.5.0.5
C46 = 10.5.0.6     C47 = 10.5.0.7     C48 = 10.5.0.8     C49 = 10.5.0.9     C50 = 10.5.0.10
```

## Routing

- **Protocol**: OSPF (Area 0)
- **Router-to-Router**: 192.168.0.0/30 link
- **OSPF Neighbors**: R1 ↔ R2
- **Client Routes**: 10.0.0.0/8 via respective gateway (eth1)
- **Internet Routes**: Default via management network (eth0)

## Files Required
```
.
├── simple-50node.yml          # Main topology file
├── daemons                    # FRR daemon config
├── r1.conf                    # Router 1 FRR config
├── r2.conf                    # Router 2 FRR config
├── deploy.sh                  # Automated deployment script
├── full-ping-matrix.sh        # Comprehensive ping test
```

## Prerequisites

- Docker installed
- Containerlab installed (`sudo clab version`)
- Open vSwitch installed (`sudo ovs-vsctl show`)

## Quick Start
```bash
# Deploy the topology
./deploy.sh

# Full matrix test (1000+ pings)
./full-ping-matrix.sh
```

## Manual Deployment
```bash
# Deploy
sudo clab deploy -t simple-50node.yml

# Wait 15 seconds, then configure (if not using deploy.sh)
# ... see deploy.sh for full configuration ...

# Verify OSPF
docker exec clab-simple50-R1 vtysh -c "show ip ospf neighbor"
docker exec clab-simple50-R1 vtysh -c "show ip route ospf"

# Test connectivity
docker exec clab-simple50-C1 ping -c 3 10.5.0.10
```

## Cleanup
```bash
# Destroy the lab
sudo clab destroy -t simple-50node.yml --cleanup
```

## Replacing Alpine with K3s Images

To use your heavy K3s images instead of Alpine:

1. **Edit `simple-50node.yml`:**
```yaml
   # BEFORE
   C1: {kind: linux, image: alpine:latest}
   
   # AFTER
   serf1:
     kind: linux
     image: your-k3s-image:tag
     env:
       CLAB_LINUX_PRIVILEGED: "true"
     binds:
       - /sys/fs/cgroup:/sys/fs/cgroup:rw
       - /lib/modules:/lib/modules:ro
       - /dev:/dev
     cmd: >
       bash -c '
         # Your K3s startup script here
         # Keep the IP address asignment COMENTED if you are using an external script for networking: # ip addr add 10.1.0.1/24 dev eth1
         # Update this part --tls-san 10.1.0.1 \ for every client based on its ip address
         # Change the enpoints name based on the new clients' names
       '
```

2. **Keep IP addressing scheme** - don't change the IPs or gateway logic

3. **Update all 50 clients** with the same pattern, adjusting IPs accordingly

---

**Created**: December 2025  
**Topology Name**: simple50  
**Total Nodes**: 57 (2 routers + 5 switches + 50 clients)
