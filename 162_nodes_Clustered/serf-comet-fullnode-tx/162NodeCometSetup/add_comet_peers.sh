#!/bin/bash

BASE_NAME="clab-century-serf"
SERF_PORT=5555
RAND=$((1 + RANDOM % 25))
CONTAINER_NAME="${BASE_NAME}${RAND}"
echo "➡ Selected container: $CONTAINER_NAME"
echo "➡ Fetching Serf members..."
RESPONSE=$(curl -s "http://${CONTAINER_NAME}:${SERF_PORT}/members")

if [[ -z "$RESPONSE" ]]; then
    echo "❌ Failed to fetch members from $CONTAINER_NAME"
    exit 1
fi

echo "✔ Members fetched."

RPC_ADDRS=$(echo "$RESPONSE" | jq -r '.[].Tags.rpc_addr')

if [[ -z "$RPC_ADDRS" ]]; then
    echo "❌ No rpc_addr found!"
    exit 1
fi

echo "➡ Found RPC addresses:"
echo "$RPC_ADDRS"
PEER_ARRAY=$(printf '%s\n' "$RPC_ADDRS" | jq -R . | jq -s .)
echo "➡ Peer array JSON = $PEER_ARRAY"
SAFE_ENCODED=$(echo "$PEER_ARRAY" \
  | sed 's/\[/\%5B/g' \
  | sed 's/\]/\%5D/g' \
  | sed 's/"/\%22/g'
)

echo "➡ Encoded peers param:"
echo "$SAFE_ENCODED"
FULL_URL="http://${CONTAINER_NAME}:26657/dial_peers?peers=${SAFE_ENCODED}&persistent=true"
echo "➡ Calling CometBFT dial_peers:"
echo "$FULL_URL"

curl -s "$FULL_URL"
echo -e "\n✔ Done!"
