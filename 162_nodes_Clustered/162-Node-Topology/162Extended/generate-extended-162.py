#!/usr/bin/env python3
"""
Generate extended-162node.yml with all 162 K3s serf nodes
Based on ip-mapping.txt and original 162nodes_ovs.yml structure
"""

def generate_serf_node(serf_num):
    """Generate YAML for a single serf node"""
    return f"""    serf{serf_num}:
      kind: linux
      image: abdullahmuzlim279/k3s-serf-node:warmcache-test
      env:
        CLAB_LINUX_PRIVILEGED: "true"
      binds:
        - scripts/init.sh:/init.sh
        - ip-mapping.txt:/ip-mapping.txt
        - /sys/fs/cgroup:/sys/fs/cgroup:rw
        - /lib/modules:/lib/modules:ro
        - /dev:/dev
      cmd: >
        bash -c '
          set -e
          echo "[INIT] Starting serf{serf_num} initialization..."
          ulimit -n 65536
          sysctl -w fs.inotify.max_user_instances=4096 2>/dev/null || true
          sysctl -w fs.inotify.max_user_watches=524288 2>/dev/null || true
          sysctl -w fs.file-max=2097152 2>/dev/null || true
          echo 0 > /sys/fs/cgroup/cpu.pressure 2>/dev/null || true
          echo 0 > /sys/fs/cgroup/memory.pressure 2>/dev/null || true
          echo "[NET] Running init.sh for IP configuration..."
          bash /init.sh
          SERF_IP=$(ip addr show eth1 | grep "inet " | awk "{{print \\$2}}" | cut -d/ -f1)
          echo "[NET] Configured IP: $SERF_IP"
          ip link set eth1 mtu 1400
          sleep $((RANDOM % 10 + 5))
          echo "[K3S] Launching K3s server for serf{serf_num}..."
          k3s server \\
            --node-name serf{serf_num} \\
            --disable traefik \\
            --disable servicelb \\
            --disable local-storage \\
            --disable metrics-server \\
            --disable-cloud-controller \\
            --disable-network-policy \\
            --disable-helm-controller \\
            --snapshotter native \\
            --tls-san $SERF_IP \\
            --kubelet-arg=cgroup-root=/ \\
            --kubelet-arg=cgroups-per-qos=false \\
            --kubelet-arg=enforce-node-allocatable= \\
            --v=0 &
          sleep 20
          chmod 666 /etc/rancher/k3s/k3s.yaml
          export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
          echo "[K3S] Waiting for containerd..."
          until /usr/local/bin/k3s ctr version >/dev/null 2>&1; do sleep 3; done
          echo "[K3S] Importing cached images..."
          for f in /opt/k3s-images/*.tar; do
            /usr/local/bin/k3s ctr images import "$f" 2>/dev/null || true
          done
          echo "[K3S] Deploying controllers..."
          k3s kubectl apply -f /tmp/qos-controller-daemonset.yaml
          k3s kubectl apply -f /tmp/service-account.yaml
          k3s kubectl apply -f /tmp/cluster-role.yaml
          k3s kubectl apply -f /tmp/cluster-role-binding.yaml
          k3s kubectl apply -f /tmp/deployment-scheduler.yaml
          k3s kubectl apply -f /tmp/ram_price.yaml
          k3s kubectl apply -f /tmp/storage_price.yaml
          k3s kubectl apply -f /tmp/vcpu_price.yaml
          k3s kubectl apply -f /tmp/vgpu_price.yaml
          mkdir -p ~/.kube
          cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
          chown $(whoami):$(whoami) ~/.kube/config 2>/dev/null || true
          chmod 600 ~/.kube/config
          echo "[READY] serf{serf_num} K3s cluster is ready!"
          while true; do sync; echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true; sleep 100000; done &
          sleep infinity
        '
"""

def generate_yaml():
    """Generate complete extended-162node.yml"""
    
    yaml_content = """name: nebula-extended
topology:
  nodes:
    #---------------------------------Switches (OVS Bridges)---------------------------------
"""
    
    # Generate 37 switches
    for i in range(1, 38):
        yaml_content += f"    switch{i}: {{kind: ovs-bridge}}\n"
    
    yaml_content += "\n    #---------------------------------Routers (FRR)---------------------------------\n"
    
    # Generate 27 routers
    for i in range(1, 28):
        yaml_content += f"""    router{i}:
      kind: linux
      image: quay.io/frrouting/frr:10.2.1
      binds:
        - router{i}/daemons:/etc/frr/daemons
        - router{i}/frr.conf:/etc/frr/frr.conf
"""
    
    yaml_content += "\n    #---------------------------------K3s Serf Nodes (162 nodes)---------------------------------\n"
    
    # Generate 162 serf nodes
    for i in range(1, 163):
        yaml_content += generate_serf_node(i)
        if i < 162:
            yaml_content += "\n"
    
    yaml_content += """
  #---------------------------------Links---------------------------------
  links:
    #---------------------------------Router2Router connections---------------------------------
    #Router1
    - endpoints: ["router1:eth1", "router2:eth1"] #
    - endpoints: ["router1:eth2", "router3:eth1"]
    #Router2
    - endpoints: ["router2:eth2", "router4:eth1"]
    #Router3
    - endpoints: ["router3:eth2", "router8:eth1"]
    #Router4
    - endpoints: ["router4:eth2", "router5:eth1"]
    - endpoints: ["router4:eth3", "router6:eth1"]
    #Router5
    - endpoints: ["router5:eth2", "router9:eth1"]
    #Router6
    - endpoints: ["router6:eth2", "router7:eth1"]
    #Router7
    - endpoints: ["router7:eth2", "router8:eth2"]
    #Router8
    - endpoints: ["router8:eth3", "router9:eth2"]
    - endpoints: ["router8:eth4", "router12:eth1"]
    - endpoints: ["router8:eth5", "router14:eth1"]
    #Router9
    - endpoints: ["router9:eth3", "router10:eth1"]
    - endpoints: ["router9:eth4", "router11:eth1"]
    #Router10
    - endpoints: ["router10:eth2", "router15:eth1"]
    #Router11
    - endpoints: ["router11:eth2", "router14:eth2"]
    #Router12
    - endpoints: ["router12:eth2", "router13:eth1"]
    #Router13
    - endpoints: ["router13:eth2", "router14:eth3"]
    - endpoints: ["router13:eth3", "router16:eth1"]
    #Router14
    - endpoints: ["router14:eth4", "router15:eth2"]
    #Router15
    - endpoints: ["router15:eth3", "router17:eth1"]
    #Router16 => no new connections
    #Router17
    - endpoints: ["router17:eth2", "router18:eth1"]
    - endpoints: ["router17:eth3", "router19:eth1"]
    - endpoints: ["router17:eth4", "router20:eth1"]
    - endpoints: ["router17:eth5", "router25:eth1"]
    #Router18
    - endpoints: ["router18:eth2", "router20:eth2"]
    #Router19
    - endpoints: ["router19:eth2", "router24:eth1"]
    #Router20
    - endpoints: ["router20:eth3", "router21:eth1"]
    - endpoints: ["router20:eth4", "router22:eth1"]
    - endpoints: ["router20:eth5", "router23:eth1"]
    - endpoints: ["router20:eth6", "router25:eth2"]
    #Router21 => no new connections
    #Router22 => no new connections
    #Router23
    - endpoints: ["router23:eth2", "router24:eth2"]
    #Router24
    - endpoints: ["router24:eth3", "router25:eth3"]
    #Router25
    # - endpoints: ["router25:eth4", "router26:eth1"]
    #Router26 => no new connections
    #Router27 => not connected to any router

    #---------------------------------Router2Switch connections---------------------------------
    #Router1
    - endpoints: ["router1:eth3", "switch5:ovs5p1"]
    - endpoints: ["router1:eth4", "switch4:ovs4p1"]
    #Router2 => no switch connected
    #Router3
    - endpoints: ["router3:eth3", "switch15:ovs15p1"]
    #Router4
    - endpoints: ["router4:eth4", "switch6:ovs6p1"]
    - endpoints: ["router4:eth5", "switch7:ovs7p1"]
    - endpoints: ["router4:eth6", "switch8:ovs8p1"]
    - endpoints: ["router4:eth7", "switch9:ovs9p1"]
    #Router5
    - endpoints: ["router5:eth3", "switch12:ovs12p1"]
    - endpoints: ["router5:eth4", "switch13:ovs13p1"]
    - endpoints: ["router5:eth5", "switch14:ovs14p1"]
    #Router6
    - endpoints: ["router6:eth3", "switch10:ovs10p1"]
    - endpoints: ["router6:eth4", "switch11:ovs11p1"]
    #Router7 => no switch connected
    #Router8
    - endpoints: ["router8:eth6", "switch16:ovs16p1"]
    - endpoints: ["router8:eth7", "switch17:ovs17p1"]
    #Router9 => no switch connected
    #Router10
    - endpoints: ["router10:eth3", "switch23:ovs23p1"]
    #Router11
    - endpoints: ["router11:eth3", "switch18:ovs18p1"]
    - endpoints: ["router11:eth4", "switch19:ovs19p1"]
    #Router12 => no switch connected
    #Router13
    - endpoints: ["router13:eth4", "switch20:ovs20p1"]
    - endpoints: ["router13:eth5", "switch21:ovs21p1"]
    - endpoints: ["router13:eth6", "switch22:ovs22p1"]
    #Router14 => no switch connected
    #Router15 => no switch connected
    #Router16
    - endpoints: ["router16:eth2", "switch24:ovs24p1"]
    - endpoints: ["router16:eth3", "switch26:ovs26p1"]
    #Router17 => no switch connected
    #Router18 => no switch connected
    #Router19 => no switch connected
    #Router20
    - endpoints: ["router20:eth7", "switch28:ovs28p1"]
    - endpoints: ["router20:eth8", "switch32:ovs32p1"]
    - endpoints: ["router20:eth9", "switch33:ovs33p1"]
    #Router21
    - endpoints: ["router21:eth2", "switch29:ovs29p1"]
    - endpoints: ["router21:eth3", "switch30:ovs30p1"]
    #Router22
    - endpoints: ["router22:eth2", "switch27:ovs27p1"]
    #Router23 => no switch connected
    #Router24 => no switch connected
    #Router25
    - endpoints: ["router25:eth4", "switch34:ovs34p1"]
    - endpoints: ["router25:eth5", "switch35:ovs35p1"]
    - endpoints: ["router25:eth6", "switch36:ovs36p1"]
    #Router26
    - endpoints: ["router26:eth1", "switch33:ovs33p2"]
    - endpoints: ["router26:eth2", "switch34:ovs34p2"]
    #Router27
    - endpoints: ["router27:eth1", "switch34:ovs34p3"]
    - endpoints: ["router27:eth2", "switch35:ovs35p2"]
    - endpoints: ["router27:eth3", "switch36:ovs36p2"]
    - endpoints: ["router27:eth4", "switch37:ovs37p1"]

    #---------------------------------Switch2Switch connections---------------------------------
    #Switch1
    - endpoints: ["switch1:ovs1p1", "switch2:ovs2p1"]
    #Switch2
    - endpoints: ["switch2:ovs2p2", "switch3:ovs3p1"]
    #Switch3
    - endpoints: ["switch3:ovs3p2", "switch4:ovs4p2"]
    #Switch24
    - endpoints: ["switch24:ovs24p2", "switch25:ovs25p1"]
    #Switch25
    - endpoints: ["switch25:ovs25p2", "switch26:ovs26p2"]
    #Switch30
    - endpoints: ["switch30:ovs30p2", "switch31:ovs31p1"]

    #---------------------------------SerfNode2Switch connections---------------------------------
    #Switch1
    - endpoints: ["switch1:ovs1p2", "serf1:eth1"]
    - endpoints: ["switch1:ovs1p3", "serf2:eth1"]
    - endpoints: ["switch1:ovs1p4", "serf3:eth1"]
    - endpoints: ["switch1:ovs1p5", "serf4:eth1"]
    - endpoints: ["switch1:ovs1p6", "serf5:eth1"]
    #Switch2
    - endpoints: ["switch2:ovs2p3", "serf6:eth1"]
    - endpoints: ["switch2:ovs2p4", "serf7:eth1"]
    - endpoints: ["switch2:ovs2p5", "serf8:eth1"]
    #Switch3
    - endpoints: ["switch3:ovs3p3", "serf9:eth1"]
    - endpoints: ["switch3:ovs3p4", "serf10:eth1"]
    - endpoints: ["switch3:ovs3p5", "serf11:eth1"]
    #Switch4
    - endpoints: ["switch4:ovs4p3", "serf12:eth1"]
    - endpoints: ["switch4:ovs4p4", "serf13:eth1"]
    - endpoints: ["switch4:ovs4p5", "serf14:eth1"]
    #Switch5
    - endpoints: ["switch5:ovs5p2", "serf15:eth1"]
    #Switch6
    - endpoints: ["switch6:ovs6p2", "serf22:eth1"]
    - endpoints: ["switch6:ovs6p3", "serf23:eth1"]
    - endpoints: ["switch6:ovs6p4", "serf24:eth1"]
    - endpoints: ["switch6:ovs6p5", "serf25:eth1"]
    #Switch7
    - endpoints: ["switch7:ovs7p2", "serf26:eth1"]
    #Switch8
    - endpoints: ["switch8:ovs8p2", "serf27:eth1"]
    - endpoints: ["switch8:ovs8p3", "serf28:eth1"]
    - endpoints: ["switch8:ovs8p4", "serf29:eth1"]
    #Switch9
    - endpoints: ["switch9:ovs9p2", "serf20:eth1"]
    - endpoints: ["switch9:ovs9p3", "serf21:eth1"]
    #Switch10
    - endpoints: ["switch10:ovs10p2", "serf33:eth1"]
    - endpoints: ["switch10:ovs10p3", "serf34:eth1"]
    #Switch11
    - endpoints: ["switch11:ovs11p2", "serf35:eth1"]
    - endpoints: ["switch11:ovs11p3", "serf36:eth1"]
    - endpoints: ["switch11:ovs11p4", "serf37:eth1"]
    - endpoints: ["switch11:ovs11p5", "serf38:eth1"]
    - endpoints: ["switch11:ovs11p6", "serf39:eth1"]
    - endpoints: ["switch11:ovs11p7", "serf40:eth1"]
    - endpoints: ["switch11:ovs11p8", "serf41:eth1"]
    - endpoints: ["switch11:ovs11p9", "serf42:eth1"]
    #Switch12
    - endpoints: ["switch12:ovs12p2", "serf43:eth1"]
    - endpoints: ["switch12:ovs12p3", "serf44:eth1"]
    - endpoints: ["switch12:ovs12p4", "serf45:eth1"]
    #Switch13
    - endpoints: ["switch13:ovs13p2", "serf46:eth1"]
    #Switch1
    - endpoints: ["switch14:ovs14p2", "serf47:eth1"]
    #Switch15
    - endpoints: ["switch15:ovs15p2", "serf51:eth1"]
    #Switch16
    - endpoints: ["switch16:ovs16p2", "serf62:eth1"]
    #Switch17
    - endpoints: ["switch17:ovs17p2", "serf63:eth1"]
    #Switch18
    - endpoints: ["switch18:ovs18p2", "serf64:eth1"]
    #Switch19
    - endpoints: ["switch19:ovs19p2", "serf65:eth1"]
    #Switch20
    - endpoints: ["switch20:ovs20p2", "serf66:eth1"]
    - endpoints: ["switch20:ovs20p3", "serf67:eth1"]
    - endpoints: ["switch20:ovs20p4", "serf68:eth1"]
    #Switch21
    - endpoints: ["switch21:ovs21p2", "serf69:eth1"]
    - endpoints: ["switch21:ovs21p3", "serf70:eth1"]
    - endpoints: ["switch21:ovs21p4", "serf71:eth1"]
    - endpoints: ["switch21:ovs21p5", "serf72:eth1"]
    - endpoints: ["switch21:ovs21p6", "serf73:eth1"]
    - endpoints: ["switch21:ovs21p7", "serf74:eth1"]
    - endpoints: ["switch21:ovs21p8", "serf75:eth1"]
    - endpoints: ["switch21:ovs21p9", "serf76:eth1"]
    - endpoints: ["switch21:ovs21p10", "serf77:eth1"]
    - endpoints: ["switch21:ovs21p11", "serf78:eth1"]
    - endpoints: ["switch21:ovs21p12", "serf79:eth1"]
    #Switch22
    - endpoints: ["switch22:ovs22p2", "serf80:eth1"]
    #Switch23
    - endpoints: ["switch23:ovs23p2", "serf82:eth1"]
    #Switch24
    - endpoints: ["switch24:ovs24p3", "serf83:eth1"]
    - endpoints: ["switch24:ovs24p4", "serf84:eth1"]
    - endpoints: ["switch24:ovs24p5", "serf85:eth1"]
    #Switch25
    - endpoints: ["switch25:ovs25p3", "serf86:eth1"]
    #Switch26
    - endpoints: ["switch26:ovs26p3", "serf87:eth1"]
    - endpoints: ["switch26:ovs26p4", "serf88:eth1"]
    - endpoints: ["switch26:ovs26p5", "serf89:eth1"]
    #Switch27
    - endpoints: ["switch27:ovs27p2", "serf96:eth1"]
    - endpoints: ["switch27:ovs27p3", "serf97:eth1"]
    - endpoints: ["switch27:ovs27p4", "serf98:eth1"]
    #Switch28
    - endpoints: ["switch28:ovs28p2", "serf112:eth1"]
    - endpoints: ["switch28:ovs28p3", "serf113:eth1"]
    - endpoints: ["switch28:ovs28p4", "serf114:eth1"]
    #Switch29
    - endpoints: ["switch29:ovs29p2", "serf115:eth1"]
    - endpoints: ["switch29:ovs29p3", "serf116:eth1"]
    #Switch30
    - endpoints: ["switch30:ovs30p3", "serf117:eth1"]
    #Switch31
    - endpoints: ["switch31:ovs31p2", "serf118:eth1"]
    - endpoints: ["switch31:ovs31p3", "serf119:eth1"]
    - endpoints: ["switch31:ovs31p4", "serf120:eth1"]
    #Switch32
    - endpoints: ["switch32:ovs32p2", "serf128:eth1"]
    #Switch33
    - endpoints: ["switch33:ovs33p3", "serf129:eth1"]
    #Switch34
    - endpoints: ["switch34:ovs34p4", "serf130:eth1"]
    - endpoints: ["switch34:ovs34p5", "serf131:eth1"]
    - endpoints: ["switch34:ovs34p6", "serf132:eth1"]
    - endpoints: ["switch34:ovs34p7", "serf133:eth1"]
    - endpoints: ["switch34:ovs34p8", "serf134:eth1"]
    - endpoints: ["switch34:ovs34p9", "serf135:eth1"]
    - endpoints: ["switch34:ovs34p10", "serf136:eth1"]
    - endpoints: ["switch34:ovs34p11", "serf137:eth1"]
    - endpoints: ["switch34:ovs34p12", "serf138:eth1"]
    - endpoints: ["switch34:ovs34p13", "serf139:eth1"]
    - endpoints: ["switch34:ovs34p14", "serf140:eth1"]
    - endpoints: ["switch34:ovs34p15", "serf141:eth1"]
    #Switch35
    - endpoints: ["switch35:ovs35p3", "serf142:eth1"]
    - endpoints: ["switch35:ovs35p4", "serf143:eth1"]
    - endpoints: ["switch35:ovs35p5", "serf144:eth1"]
    - endpoints: ["switch35:ovs35p6", "serf145:eth1"]
    - endpoints: ["switch35:ovs35p7", "serf146:eth1"]
    #Switch36
    - endpoints: ["switch36:ovs36p3", "serf147:eth1"]
    - endpoints: ["switch36:ovs36p4", "serf148:eth1"]
    - endpoints: ["switch36:ovs36p5", "serf149:eth1"]
    - endpoints: ["switch36:ovs36p6", "serf150:eth1"]
    - endpoints: ["switch36:ovs36p7", "serf151:eth1"]
    - endpoints: ["switch36:ovs36p8", "serf152:eth1"]
    - endpoints: ["switch36:ovs36p9", "serf153:eth1"]
    - endpoints: ["switch36:ovs36p10", "serf154:eth1"]
    - endpoints: ["switch36:ovs36p11", "serf155:eth1"]
    - endpoints: ["switch36:ovs36p12", "serf156:eth1"]
    #Switch37
    - endpoints: ["switch37:ovs37p2", "serf162:eth1"]

    #---------------------------------SerfNode2Router connections---------------------------------
    #Router1
    - endpoints: ["router1:eth5", "serf16:eth1"]
    - endpoints: ["router1:eth6", "serf17:eth1"]
    #Router2
    - endpoints: ["router2:eth3", "serf18:eth1"]
    - endpoints: ["router2:eth4", "serf19:eth1"]
    #Router3
    - endpoints: ["router3:eth4", "serf52:eth1"]
    - endpoints: ["router3:eth5", "serf53:eth1"]
    - endpoints: ["router3:eth6", "serf54:eth1"]
    - endpoints: ["router3:eth7", "serf55:eth1"]
    - endpoints: ["router3:eth8", "serf56:eth1"]
    #Router4
    - endpoints: ["router4:eth8", "serf30:eth1"]
    - endpoints: ["router4:eth9", "serf31:eth1"]
    - endpoints: ["router4:eth10", "serf32:eth1"]
    #Router5
    - endpoints: ["router5:eth6", "serf48:eth1"]
    - endpoints: ["router5:eth7", "serf49:eth1"]
    - endpoints: ["router5:eth8", "serf50:eth1"]
    #Router6 => no connected serf nodes
    #Router7 => no connected serf nodes
    #Router8
    - endpoints: ["router8:eth8", "serf57:eth1"]
    - endpoints: ["router8:eth9", "serf58:eth1"]
    - endpoints: ["router8:eth10", "serf59:eth1"]
    - endpoints: ["router8:eth11", "serf60:eth1"]
    - endpoints: ["router8:eth12", "serf61:eth1"]
    #Router9 => no connected serf nodes
    #Router10 => no connected serf nodes
    #Router11 => no connected serf nodes
    #Router12 => no connected serf nodes
    #Router13
    - endpoints: ["router13:eth7", "serf81:eth1"]
    #Router14 => no connected serf nodes
    #Router15 => no connected serf nodes
    #Router16
    - endpoints: ["router16:eth4", "serf90:eth1"]
    - endpoints: ["router16:eth5", "serf91:eth1"]
    - endpoints: ["router16:eth6", "serf92:eth1"]
    - endpoints: ["router16:eth7", "serf93:eth1"]
    - endpoints: ["router16:eth8", "serf94:eth1"]
    - endpoints: ["router16:eth9", "serf95:eth1"]
    #Router17
    - endpoints: ["router17:eth6", "serf104:eth1"]
    - endpoints: ["router17:eth7", "serf105:eth1"]
    #Router18 => no connected serf nodes
    #Router19 => no connected serf nodes
    #Router20
    - endpoints: ["router20:eth10", "serf106:eth1"]
    - endpoints: ["router20:eth11", "serf107:eth1"]
    - endpoints: ["router20:eth12", "serf108:eth1"]
    - endpoints: ["router20:eth13", "serf109:eth1"]
    - endpoints: ["router20:eth14", "serf110:eth1"]
    - endpoints: ["router20:eth15", "serf111:eth1"]
    #Router21 => no connected serf nodes
    #Router22
    - endpoints: ["router22:eth3", "serf99:eth1"]
    - endpoints: ["router22:eth4", "serf100:eth1"]
    - endpoints: ["router22:eth5", "serf101:eth1"]
    - endpoints: ["router22:eth6", "serf102:eth1"]
    - endpoints: ["router22:eth7", "serf103:eth1"]
    #Router23
    - endpoints: ["router23:eth3", "serf121:eth1"]
    - endpoints: ["router23:eth4", "serf122:eth1"]
    - endpoints: ["router23:eth5", "serf123:eth1"]
    - endpoints: ["router23:eth6", "serf124:eth1"]
    #Router24
    - endpoints: ["router24:eth4", "serf125:eth1"]
    - endpoints: ["router24:eth5", "serf126:eth1"]
    #Router25
    - endpoints: ["router25:eth7", "serf127:eth1"]
    #Router26 => no connected serf nodes
    #Router27
    - endpoints: ["router27:eth5", "serf157:eth1"]
    - endpoints: ["router27:eth6", "serf158:eth1"]
    - endpoints: ["router27:eth7", "serf159:eth1"]
    - endpoints: ["router27:eth8", "serf160:eth1"]
    - endpoints: ["router27:eth9", "serf161:eth1"]

"""
    
    return yaml_content

if __name__ == "__main__":
    print("Generating extended-162node.yml...")
    yaml_content = generate_yaml()
    
    with open("extended-162node.yml", "w") as f:
        f.write(yaml_content)
    
    print("✓ Generated extended-162node.yml")
    print(f"  Total size: {len(yaml_content)} characters")
    print("  Ready for deployment!")