#!/usr/bin/env python3
import os
import threading
import json
import subprocess
from pathlib import Path
from flask import Flask, request, jsonify, send_file
import yaml
import requests
import re
import redis
import time

app = Flask(__name__)

# Base folder for storing fetched kubeconfigs
BASE_DIR = Path("connections")
BASE_DIR.mkdir(exist_ok=True)

# Default kubeconfig path for k3s
LOCAL_K3S_CONFIG = "/etc/rancher/k3s/k3s.yaml"

REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
REDIS_CHANNEL = "liqo:initiate"

# Node-IP map (Not used anymore since Redis gives the IP. To be Removed)
NODE_IP_MAP = {
    "clab-century-serf1": "10.0.1.11",
    "clab-century-serf2": "10.0.1.12",
    "clab-century-serf3": "10.0.1.13",
    "clab-century-serf4": "10.0.1.14",
    "clab-century-serf5": "10.0.1.15",
    "clab-century-serf6": "10.0.1.16",
    "clab-century-serf7": "10.0.1.17",
    "clab-century-serf8": "10.0.1.18",
    "clab-century-serf9": "10.0.1.19",
    "clab-century-serf10": "10.0.1.20",
    "clab-century-serf11": "10.0.1.21",
    "clab-century-serf12": "10.0.1.22",
    "clab-century-serf13": "10.0.2.11",
    "clab-century-serf14": "10.0.2.12",
    "clab-century-serf15": "10.0.2.13",
    "clab-century-serf16": "10.0.2.14",
    "clab-century-serf17": "10.0.2.15",
    "clab-century-serf18": "10.0.2.16",
    "clab-century-serf19": "10.0.2.17",
    "clab-century-serf20": "10.0.2.18",
    "clab-century-serf21": "10.0.2.19",
    "clab-century-serf22": "10.0.2.20",
    "clab-century-serf23": "10.0.2.21",
    "clab-century-serf24": "10.0.2.22",
    "clab-century-serf25": "10.0.2.23",
}

# ----------------------------
# Utility functions
# ----------------------------
def validate_configs(config1: str, config2: str):
    for cfg in [config1, config2]:
        if not Path(cfg).is_file():
            raise FileNotFoundError(f"{cfg} does not exist.")
            
def get_local_api_ip():
    """Extract local API server IP from k3s.yaml"""
    try:
        with open(LOCAL_K3S_CONFIG, "r") as f:
            cfg = yaml.safe_load(f)
        server_url = cfg["clusters"][0]["cluster"]["server"]
        # Extract the IP between https:// and :6443
        match = re.search(r"https://([\d\.]+):\d+", server_url)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"Error extracting IP from kubeconfig: {e}")
    return None


def stream_command(cmd):
    """Run command and stream output live"""
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    for line in process.stdout:
        print(line, end="")
    process.wait()
    return process.returncode


def run_command_capture(cmd):
    """Run a shell command and return output text"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.stdout.strip()
    except Exception as e:
        return f"Error running command: {e}"


def peer_clusters(config1: str, config2: str):
    validate_configs(config1, config2)
    cmd = [
        "liqoctl", "peer",
        f"--kubeconfig={config1}",
        f"--remote-kubeconfig={config2}",
        "--gw-server-service-type=NodePort"
    ]
    print(f"Running: {' '.join(cmd)}")
    return stream_command(cmd)


def unpeer_clusters(config1: str, config2: str):
    validate_configs(config1, config2)
    cmd = [
        "liqoctl", "unpeer",
        f"--kubeconfig={config1}",
        f"--remote-kubeconfig={config2}",
    ]
    print(f"Running: {' '.join(cmd)}")
    return stream_command(cmd)


def patch_kubeconfig(original: str, server_ip: str, dest: Path):
    """Replace server address in kubeconfig with seller_ip and save"""
    with open(original, "r") as f:
        cfg = yaml.safe_load(f)

    for cluster in cfg.get("clusters", []):
        server = cluster["cluster"]["server"]
        parts = server.split("//")
        if len(parts) == 2:
            protocol, address = parts
            host_port = address.split(":")
            if len(host_port) == 2:
                _, port = host_port
                new_server = f"{protocol}//{server_ip}:{port}"
            else:
                new_server = f"{protocol}//{server_ip}"
            cluster["cluster"]["server"] = new_server

    with open(dest, "w") as f:
        yaml.safe_dump(cfg, f)
    return dest


def get_liqo_status():
    """Run `liqoctl info` and extract basic status information cleanly."""
    cmd = ["liqoctl", "info", "--kubeconfig", LOCAL_K3S_CONFIG]
    output = run_command_capture(cmd)

    # Remove box drawing characters and normalize
    clean_output = (
        output
        .replace("│", "")
        .replace("┌", "")
        .replace("└", "")
        .replace("─", "")
        .replace("┘", "")
        .replace("┐", "")
    )

    # Extract Cluster ID
    cluster_id_match = re.search(r"Cluster ID:\s*([A-Za-z0-9\-]+)", clean_output)
    cluster_id = cluster_id_match.group(1) if cluster_id_match else None

    # Detect Liqo health
    if "Liqo is healthy" in clean_output:
        liqo_health = "healthy"
    elif "Liqo is not healthy" in clean_output:
        liqo_health = "unhealthy"
    else:
        liqo_health = "unknown"

    # Extract Active peerings section
    peerings_section = re.search(r"Active peerings(.*)", clean_output, re.S)
    active_peerings = 0
    if peerings_section:
        text = peerings_section.group(1)
        # Count lines that look like peer IDs (non-empty, not headers)
        for line in text.splitlines():
            line = line.strip()
            if line and not line.lower().startswith(("role:", "networking", "authentication", "offloading")):
                # Ignore section headers, count cluster IDs
                if re.match(r"^[A-Za-z0-9\-]+$", line):
                    active_peerings += 1

    return {
        "cluster_id": cluster_id,
        "liqo_health": liqo_health,
        "active_peerings": active_peerings,
        "raw_output": clean_output.strip(),
    }


# ----------------------------
# Flask endpoints
# ----------------------------
@app.route("/send-config", methods=["GET"])
def send_config():
    """Seller endpoint: send kubeconfig to buyer"""
    kubeconfig_path = LOCAL_K3S_CONFIG
    if not Path(kubeconfig_path).is_file():
        return jsonify({"error": "k3s kubeconfig not found"}), 404
    return send_file(kubeconfig_path, as_attachment=True, download_name="k3s.yaml")


@app.route("/connect", methods=["POST"])
def connect():
    """Buyer endpoint: fetch kubeconfig from seller and peer"""
    data = request.json
    seller_ip = data["seller_ip"]

    # Fetch kubeconfig from seller
    url = f"http://{seller_ip}:5000/send-config"
    resp = requests.get(url)
    if resp.status_code != 200:
        return jsonify({"error": f"Failed to fetch kubeconfig from {seller_ip}"}), 500

    # Save configs
    seller_folder = BASE_DIR / seller_ip
    seller_folder.mkdir(exist_ok=True)
    raw_path = seller_folder / "raw.yaml"
    fixed_path = seller_folder / "fixed.yaml"

    with open(raw_path, "wb") as f:
        f.write(resp.content)

    # Patch kubeconfig to use seller_ip
    patch_kubeconfig(str(raw_path), seller_ip, fixed_path)

    # Run liqoctl peer
    rc = peer_clusters(LOCAL_K3S_CONFIG, str(fixed_path))
    return jsonify({"status": "success" if rc == 0 else "failed"})


@app.route("/disconnect", methods=["POST"])
def disconnect():
    """Buyer endpoint: remove peering with seller"""
    data = request.json
    seller_ip = data["seller_ip"]

    fixed_path = BASE_DIR / seller_ip / "fixed.yaml"
    if not fixed_path.exists():
        return jsonify({"error": "No saved kubeconfig for this seller"}), 404

    rc = unpeer_clusters(LOCAL_K3S_CONFIG, str(fixed_path))
    return jsonify({"status": "success" if rc == 0 else "failed"})


@app.route("/status", methods=["GET"])
def status():
    """Health check + Liqo status"""
    kubeconfig_exists = Path(LOCAL_K3S_CONFIG).is_file()
    liqo_info = get_liqo_status() if kubeconfig_exists else None

    return jsonify({
        "status": "ok",
        "kubeconfig_exists": kubeconfig_exists,
        "local_kubeconfig": LOCAL_K3S_CONFIG,
        "liqo": liqo_info
    })


# ----------------------------
# Redis Listener
# ----------------------------
def redis_listener():
    local_ip = get_local_api_ip()
    print(f"[INFO] Local node API IP detected: {local_ip}")

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe(REDIS_CHANNEL)
    print(f"[INFO] Subscribed to Redis channel: {REDIS_CHANNEL}")

    for message in pubsub.listen():
        if message["type"] != "message":
            continue

        try:
            data = json.loads(message["data"])
            print(f"[REDIS] Received message: {data}")

            if data.get("type") == "transfer":
                buyer_ip = data.get("buyer_ip")
                seller_ip = data.get("seller_ip")
                
                if not buyer_ip or not seller_ip:
                    print(f"[WARN] Missing buyer_ip or seller_ip in message: {data}")
                    continue
                
                # Only run if this node is the buyer
                if buyer_ip != local_ip:
                    print(f"[SKIP] Local IP {local_ip} != buyer IP {buyer_ip}")
                    continue

                print(f"[CONNECT] Initiating connection: {buyer_ip} <- {seller_ip}")
                url = f"http://{buyer_ip}:5000/connect"
                payload = {"seller_ip": seller_ip}

                try:
                    resp = requests.post(url, json=payload, timeout=10)
                    print(f"[OK] Response: {resp.status_code} {resp.text}")
                except Exception as e:
                    print(f"[ERROR] Error connecting {buyer_ip} -> {seller_ip}: {e}")

        except Exception as e:
            print(f"[ERROR] Error handling Redis message: {e}")



# ----------------------------
# Entry Point
# ----------------------------
if __name__ == "__main__":
    # Run Redis listener in background thread
    t = threading.Thread(target=redis_listener, daemon=True)
    t.start()

    app.run(host="0.0.0.0", port=5000, debug=False)
