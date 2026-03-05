# setup_liqo_api.sh – Liqo API Deployment Script

## Overview
The `setup_liqo_api.sh` script automates the **installation** or **reset** of the `liqo_api.py` Flask service across multiple k3s container nodes.  
It ensures that each node has Python and all required dependencies installed, the API script is copied, and the Flask service is restarted.

This script is particularly useful for managing distributed testbed environments or containerized clusters where you need to maintain consistent API services across multiple nodes.

---

## Usage

```bash
./setup_liqo_api.sh <action>
```

### Supported Actions

| Action | Description |
|---------|--------------|
| `install` | Installs Python, pip, and all necessary Python dependencies (`flask`, `pyyaml`, `requests`), copies the API script, and starts the Flask service. |
| `reset` | Stops any running `liqo_api.py` processes, replaces the script with the latest version, and restarts the service (without reinstalling dependencies). |

### Examples

```bash
# Perform a full installation on all nodes
./setup_liqo_api.sh install

# Reset the service (restart with updated API script)
./setup_liqo_api.sh reset
```

---

## Script Parameters and Variables

| Variable | Description |
|-----------|--------------|
| `ACTION` | User-supplied command-line argument (`install` or `reset`). |
| `NODES` | List of container names where the API should be deployed. Modify this array to match your environment. |
| `API_FILE` | Local path to the Flask service script (`liqo_api.py`). Must exist in the same directory as this setup script. |

---

## Functional Breakdown

### 1. Input Validation
The script first checks whether an action parameter was provided.  
If not, it displays an error message and usage instructions.

### 2. File Existence Check
Before proceeding, it ensures that `liqo_api.py` is present in the current directory.

### 3. Node Loop
The script iterates through all container nodes defined in the `NODES` array.

Each iteration performs the following steps:

#### a. Installation (only for `install` action)
Installs Python 3, pip, and required packages inside the container.

#### b. Copy Flask Script
Copies the local `liqo_api.py` file to `/root/liqo_api.py` inside the container.

#### c. Stop Running API Process
Stops any previously running instance of the Flask service (if present).

#### d. Start New API Instance
Runs the Flask application in the background using `nohup` so it continues running after the script exits.

---

### 4. Completion Message
After all nodes are processed, the script prints a summary message.

---

## Verification

You can verify that the Flask service is running on a node by sending a request to its `/status` endpoint:

```bash
curl http://<node_ip>:5000/status
```

Expected response: a JSON or text message indicating the service status (depends on your `liqo_api.py` implementation).

---

## Error Handling

| Scenario | Behavior |
|-----------|-----------|
| Missing argument | Script exits with an error and usage instructions. |
| Missing `liqo_api.py` | Script aborts with an error message. |
| Node not accessible | Docker errors will be displayed for that node; script continues with the next one. |

---

## Customization

- **Modify Node List:**  
  Update the `NODES` array to match your own k3s container names.
  
- **Change Script Path:**  
  Adjust `API_FILE` or the destination path `/root/liqo_api.py` if your environment differs.

- **Additional Dependencies:**  
  Add more packages to the pip install command inside the `install` section if your Flask app requires them.

---
---


# liqo_api.py – Liqo API Service

## Overview
`liqo_api.py` is a lightweight **Flask-based REST API** designed to manage **Liqo cluster peering** between distributed Kubernetes (k3s) environments.  
It acts as a local agent running inside each node container, enabling clusters to:
- Expose their own kubeconfig file to peers (sellers).
- Fetch kubeconfigs from other nodes and establish peering (buyers).
- Unpeer or disconnect from other clusters.
- Query the current Liqo status and active peerings.

This service runs on **port 5000** by default and is intended to be deployed automatically using the `setup_liqo_api.sh` script.

---

## Architecture

Each node runs one instance of `liqo_api.py`.  
The service supports **two roles** in a peering interaction:

- **Seller node:** Responds to `/send-config` requests to share its kubeconfig.
- **Buyer node:** Initiates a `/connect` request to the seller to fetch its kubeconfig and peer clusters.

### Basic Workflow
1. Node A (buyer) sends a POST request to Node B (seller) at `/send-config`.
2. Node B returns its kubeconfig.
3. Node A patches the kubeconfig (replaces localhost or hostname with Node B’s IP).
4. Node A runs `liqoctl peer` to establish a connection.
5. Either node can later run `/disconnect` to unpeer.

---

## Dependencies

### Python Libraries
- **Flask** – HTTP server and REST API framework  
- **PyYAML** – for parsing and writing kubeconfig files  
- **Requests** – for making HTTP requests to other nodes  
- **subprocess, os, pathlib, re** – for command execution, filesystem operations, and parsing  

### External Commands
- **`liqoctl`** – CLI tool required for cluster peering and unpeering  
- **`k3s`** – local Kubernetes instance that generates `/etc/rancher/k3s/k3s.yaml`

---

## Directory Structure

At runtime, the service creates a base directory for storing peer kubeconfigs:

```
connections/
 └── <seller_ip>/
     ├── raw.yaml   # Original kubeconfig fetched from seller
     └── fixed.yaml # Patched version with seller’s IP
```

---

## Configuration

| Constant | Description |
|-----------|--------------|
| `BASE_DIR` | Root folder for storing fetched kubeconfigs (`connections/`). Automatically created on startup. |
| `LOCAL_K3S_CONFIG` | Path to the local node’s kubeconfig file (`/etc/rancher/k3s/k3s.yaml`). Used for Liqo operations. |

---

## Utility Functions

### `validate_configs(config1, config2)`
Checks that both provided kubeconfig files exist.  
Raises `FileNotFoundError` if any file is missing.

---

### `stream_command(cmd)`
Runs a shell command and streams its live output line by line to stdout.  
Used for long-running operations like `liqoctl peer`.

Returns the **exit code** of the command.

---

### `run_command_capture(cmd)`
Runs a shell command, waits for completion, and returns its stdout as text.  
Used for short commands like `liqoctl info`.

Returns a string (command output or error message).

---

### `peer_clusters(config1, config2)`
Executes:

```bash
liqoctl peer --kubeconfig=<config1> --remote-kubeconfig=<config2> --gw-server-service-type=NodePort
```

This establishes a Liqo peering between the **local cluster** and the **remote cluster**.

---

### `unpeer_clusters(config1, config2)`
Executes:

```bash
liqoctl unpeer --kubeconfig=<config1> --remote-kubeconfig=<config2>
```

Used to remove a peering relationship.

---

### `patch_kubeconfig(original, server_ip, dest)`
Rewrites the `server` field inside a kubeconfig file so it points to the **seller’s public IP** instead of `localhost` or a hostname.

Example transformation:

```yaml
# Before
server: https://127.0.0.1:6443

# After
server: https://10.0.0.2:6443
```

The patched kubeconfig is saved to `dest` and returned.

---

### `get_liqo_status()`
Runs `liqoctl info` and parses its output to extract key details:
- **Cluster ID**
- **Liqo health status** (`healthy`, `unhealthy`, or `unknown`)
- **Number of active peerings**

It also cleans up terminal box-drawing characters for readability and returns a structured JSON object:

```json
{
  "cluster_id": "a1b2c3",
  "liqo_health": "healthy",
  "active_peerings": 2,
  "raw_output": "Liqo is healthy..."
}
```

---

## API Endpoints

### 1. `/send-config`  
**Method:** `GET`  
**Role:** Seller  

Returns the local node’s kubeconfig file for remote download.

**Response:**
- 200: Returns kubeconfig file (`k3s.yaml`) as attachment.  
- 404: If the local kubeconfig is missing.

Example:
```bash
curl http://<seller_ip>:5000/send-config -O
```

---

### 2. `/connect`  
**Method:** `POST`  
**Role:** Buyer  

Fetches the seller’s kubeconfig and initiates a Liqo peering.

**Request JSON:**
```json
{
  "seller_ip": "10.0.0.2"
}
```

**Workflow:**
1. Downloads kubeconfig from `http://<seller_ip>:5000/send-config`
2. Saves it as `connections/<seller_ip>/raw.yaml`
3. Patches the kubeconfig to replace server hostname with the seller’s IP
4. Saves patched version to `connections/<seller_ip>/fixed.yaml`
5. Runs `liqoctl peer` to establish connection

**Response:**
```json
{ "status": "success" }
```
or
```json
{ "status": "failed" }
```

---

### 3. `/disconnect`  
**Method:** `POST`  
**Role:** Buyer  

Removes an existing peering with the given seller.

**Request JSON:**
```json
{
  "seller_ip": "10.0.0.2"
}
```

**Behavior:**
- Looks up the patched kubeconfig (`fixed.yaml`) for that seller.
- Runs `liqoctl unpeer` to remove the connection.

**Response:**
```json
{ "status": "success" }
```
or
```json
{ "error": "No saved kubeconfig for this seller" }
```

---

### 4. `/status`  
**Method:** `GET`  
**Role:** Any  

Provides health information about the local node’s Liqo environment.

**Response Example:**
```json
{
  "status": "ok",
  "kubeconfig_exists": true,
  "local_kubeconfig": "/etc/rancher/k3s/k3s.yaml",
  "liqo": {
    "cluster_id": "7c47a8b1",
    "liqo_health": "healthy",
    "active_peerings": 3,
    "raw_output": "Liqo is healthy..."
  }
}
```

---

## Service Execution

At the bottom of the file:
```python
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```

This ensures the Flask server:
- Listens on all interfaces (`0.0.0.0`)
- Runs on port `5000`
- Starts automatically when executed as a script

Logs are typically redirected to `/root/liqo_api.log` by the setup script.

---

## Error Handling

| Scenario | Behavior |
|-----------|-----------|
| Missing kubeconfig file | Returns JSON 404 error |
| Invalid or unreachable seller | Returns 500 error |
| Command failures (`liqoctl`) | Returns status `"failed"` |
| Missing connection folder | Automatically created when needed |

---

## Example Interaction

**Step 1 – Buyer connects to seller**

```bash
curl -X POST http://10.0.0.1:5000/connect -H "Content-Type: application/json"   -d '{"seller_ip": "10.0.0.2"}'
```

**Step 2 – Check status**

```bash
curl http://10.0.0.1:5000/status
```

**Step 3 – Disconnect**

```bash
curl -X POST http://10.0.0.1:5000/disconnect -H "Content-Type: application/json"   -d '{"seller_ip": "10.0.0.2"}'
```

---

**Intended use case:**  
Run one instance per node in a k3s-based Liqo deployment to enable on-demand, programmatic peering between edge or distributed clusters.
