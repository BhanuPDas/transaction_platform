# Docker & Liqo API Setup Guide

This guide provides step-by-step instructions for preparing your Docker environment, managing Docker logs, and deploying the Liqo API with Kubernetes. Following these steps ensures smooth operation and prevents disk space issues due to large Docker logs.

---

## Pre-Topology Setup

These steps should ideally be performed **after installing Docker but before deploying the topology**. However, they can also be applied after deployment. They are intended to prevent Docker logs from consuming excessive disk space.

### Configure Docker Logging (Dont use this one if Topology with Blockchain is already built)

1. Create or edit the Docker daemon configuration file:

```bash
sudo nano /etc/docker/daemon.json
```

**Nano key combos:**

- Save: `Ctrl + S`
- Exit: `Ctrl + X`

2. Add the following configuration in the file to limit log size:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  }
}
```

3. Restart Docker to apply the changes:

```bash
sudo systemctl restart docker
```

---

### Set Up Docker Log Monitoring Cron Job (Use in any case)

1. Create a monitoring script:

```bash
sudo nano /usr/local/bin/monitor-docker-logs.sh
```

**Nano key combos:** Save: `Ctrl + S`, Exit: `Ctrl + X`

2. Paste the following content:

```bash
#!/bin/bash
# monitor-docker-logs.sh
# Monitors Docker container logs and truncates any file larger than 400MB

THRESHOLD=$((400 * 1024 * 1024))  # 400 MB in bytes
LOG_DIR="/var/lib/docker/containers"

echo "$(date): Checking Docker logs..."

# Find all JSON logs
find "$LOG_DIR" -type f -name "*-json.log" | while read logfile; do
    SIZE=$(stat -c%s "$logfile")
    if [ "$SIZE" -ge "$THRESHOLD" ]; then
        echo "$(date): Truncating $logfile (size: $((SIZE/1024/1024)) MB)"
        truncate -s 0 "$logfile"
    fi
 done

echo "$(date): Done checking Docker logs."
```

3. Make the script executable:

```bash
sudo chmod +x /usr/local/bin/monitor-docker-logs.sh
```

4. Add a cron job to run the script every 5 minutes:

```bash
sudo crontab -e
```

- Choose nano as the editor (type `1`)
- Add the following line at the end of the file:

```bash
*/5 * * * * /usr/local/bin/monitor-docker-logs.sh >> /var/log/docker-log-monitor.log 2>&1
```

- Save and exit (`Ctrl + S`, `Ctrl + X`)

---

## Pre-Liqo API Deployment

Before deploying the Liqo API, verify that your Containerlab topology is running correctly.

### Verify Containerlab Topology

```bash
clab inspect -a
```

### Verify Serf Nodes

1. Access each Serf container:

```bash
sudo docker exec -it clab-century-serf1 bash
```

2. Check Kubernetes nodes inside the container:

```bash
k3s kubectl get nodes
```

You may see two nodes: `serf1` and `k8s2`.

3. Delete the duplicate `k8s2` node and wait for a few seconds to a minute for pods to restart:

```bash
k3s kubectl delete node k8s2
k3s kubectl get pods -A
```

If there are lingering pods in Terminating or other unusual states, consider uninstalling and reinstalling Liqo.

4. Verify Liqo status:

```bash
liqoctl info
```

Once all checks are complete, you can proceed with the Liqo API deployment.

---

## Verify Container IPs and Cluster Connectivity (Important Before API Deployment)

Each container in your topology typically has two IP addresses:

- **A 172.x.x.x IP** — part of the Docker network space
- **A 10.x.x.x IP** — part of the Containerlab topology network

The Liqo clusters must communicate using the **10.x.x.x IPs** for proper API demonstration.

---

### Step 1: Check Cluster IP Used by Liqo

Run the following command inside each cluster (for example, in `serf1`):

```bash
liqoctl info --kubeconfig /etc/rancher/k3s/k3s.yaml
```

- If the Cluster IP shown is in the **10.x.x.x range** → ✅ Perfect, no changes needed.
- If it shows a **172.x.x.x** or **127.0.0.1** IP → ⚠️ The next steps may not work comletely.

---

### Step 2: Export and Modify Kubeconfigs

From inside each container, copy the kubeconfig to your host machine:

```bash
sudo docker cp clab-century-serf1:/etc/rancher/k3s/k3s.yaml ./k3s-serf1.yaml
sudo docker cp clab-century-serf2:/etc/rancher/k3s/k3s.yaml ./k3s-serf2.yaml
```

Identify each container’s **10.x.x.x IP address (topology network)** using one of the following methods:

- Check the **topology IP change file** that lists the container IP mappings.
- Or, run the following inside the container to view network interfaces:

  ```bash
  ip addr
  ```

If you are unsure which file or IP to use, contact **Urwah** or **Zeba** to point you to the correct reference file.

Edit each kubeconfig file and replace the `server` field IP (usually `127.0.0.1` or `172.x.x.x`) with the corresponding `10.x.x.x` IP.

Example — open and edit:

```bash
nano k3s-serf1.yaml
```

Find the line:

```yaml
server: https://127.0.0.1:6443
```

Replace it with:

```yaml
server: https://10.10.0.2:6443
```

Save and exit (`Ctrl + S`, `Ctrl + X`).

---

### Step 3: Test Connectivity Using Modified Kubeconfigs

From your host machine, check that you can reach each cluster:

```bash
kubectl --kubeconfig ./k3s-serf1.yaml get nodes
kubectl --kubeconfig ./k3s-serf2.yaml get nodes
```

- If you see the cluster nodes listed → ✅ Connection works.

---

### Step 4: Test Liqo Connectivity Between Clusters

Try peering the clusters manually to confirm communication works before deploying the API:

```bash
liqoctl peer --kubeconfig ./k3s-serf1.yaml \
    --remote-kubeconfig ./k3s-serf2.yaml
```

Verify peering status:

```bash
liqoctl info --kubeconfig ./k3s-serf1.yaml
```

- If the clusters peer successfully and Liqo reports an active connection, you’re ready to deploy the Liqo API. Else you will either need to somehow configure the k3s setup to include the 10.x.x.x IP or you can for now build a hardcoded translation dictionary just to verify if the integration would work if the IPs were recognised by kubernetes.


## Deploy Liqo API

Deploy the Flask API server in your topology. Once deployed, the API allows triggering Liqo connections between buyer and seller nodes.

---

## Integration and Usage

After deployment:

1. Trigger a Liqo connection via a POST request to the buyer’s `/connect` endpoint:

```bash
curl -X POST http://localhost:5000/connect \
     -H "Content-Type: application/json" \
     -d '{"seller_ip": "x.x.x.x"}'
```

The Flask API will initiate peering and establish the connection.

2. Verify that the virtual node appears in the buyer’s Kubernetes cluster:

```bash
k3s kubectl get nodes
```

The buyer can now offload workloads using standard kubectl commands.

