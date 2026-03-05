#!/bin/bash

MODE="$1"   # "execute" or "list"

if [[ "$MODE" != "execute" && "$MODE" != "list" ]]; then
  echo "Usage: $0 [execute|list]"
  echo "  execute = run all disconnect commands"
  echo "  list    = only show commands, do NOT run them"
  exit 1
fi

# Node → IP mapping
# ------- CHANGE THE IP MAPPING WHEN REDEPLOYING OR CHANGING TOPOLOGY ------- 
declare -A NODE_IP_MAP=(
  [clab-century-serf-1]="10.1.0.1"
  [clab-century-serf-2]="10.1.0.2"
  [clab-century-serf-3]="10.1.0.3"
  [clab-century-serf-4]="10.1.0.4"
  [clab-century-serf-5]="10.1.0.5"
  [clab-century-serf-6]="10.1.0.6"
  [clab-century-serf-7]="10.1.0.7"
  [clab-century-serf-8]="10.1.0.8"
  [clab-century-serf-9]="10.1.0.9"
  [clab-century-serf-10]="10.1.0.10"

  [clab-century-serf-11]="10.2.0.1"
  [clab-century-serf-12]="10.2.0.2"
  [clab-century-serf-13]="10.2.0.3"
  [clab-century-serf-14]="10.2.0.4"
  [clab-century-serf-15]="10.2.0.5"
  [clab-century-serf-16]="10.2.0.6"
  [clab-century-serf-17]="10.2.0.7"
  [clab-century-serf-18]="10.2.0.8"
  [clab-century-serf-19]="10.2.0.9"
  [clab-century-serf-20]="10.2.0.10"

  [clab-century-serf-21]="10.3.0.1"
  [clab-century-serf-22]="10.3.0.2"
  [clab-century-serf-23]="10.3.0.3"
  [clab-century-serf-24]="10.3.0.4"
  [clab-century-serf-25]="10.3.0.5"
  [clab-century-serf-26]="10.3.0.6"
  [clab-century-serf-27]="10.3.0.7"
  [clab-century-serf-28]="10.3.0.8"
  [clab-century-serf-29]="10.3.0.9"
  [clab-century-serf-30]="10.3.0.10"

  [clab-century-serf-31]="10.4.0.1"
  [clab-century-serf-32]="10.4.0.2"
  [clab-century-serf-33]="10.4.0.3"
  [clab-century-serf-34]="10.4.0.4"
  [clab-century-serf-35]="10.4.0.5"
  [clab-century-serf-36]="10.4.0.6"
  [clab-century-serf-37]="10.4.0.7"
  [clab-century-serf-38]="10.4.0.8"
  [clab-century-serf-39]="10.4.0.9"
  [clab-century-serf-40]="10.4.0.10"

  [clab-century-serf-41]="10.5.0.1"
  [clab-century-serf-42]="10.5.0.2"
  [clab-century-serf-43]="10.5.0.3"
  [clab-century-serf-44]="10.5.0.4"
  [clab-century-serf-45]="10.5.0.5"
  [clab-century-serf-46]="10.5.0.6"
  [clab-century-serf-47]="10.5.0.7"
  [clab-century-serf-48]="10.5.0.8"
  [clab-century-serf-49]="10.5.0.9"
  [clab-century-serf-50]="10.5.0.10"

)

TOTAL_COUNT=0  # Global counter for all nodes

# ------- CHANGE THE RANGE TO THE NUMBER OF NODES ------- 
for i in $(seq 1 50); do
  NODE="clab-century-serf$i"
  echo "🔍 Checking $NODE ..."

  COUNT=0  # connection counter

  OUTPUT=$(docker exec $NODE liqoctl info 2>/dev/null)

  # Extract peers where Role = Provider (these are the sellers)
  PROVIDERS=$(echo "$OUTPUT" | awk '
    /^ *\|  clab-serf-/ { gsub(/[| ]/,"",$2); peer=$2 } 
    /Role:[ ]*Provider/ { print peer }
  ')

  for P in $PROVIDERS; do
    ((COUNT++))  # increment counter
    ((TOTAL_COUNT++))

    # Normalize name to match NODE_IP_MAP
    SELLER_NODE="clab-century-${P#clab-}"
    SELLER_IP=${NODE_IP_MAP[$SELLER_NODE]}

    if [ -n "$SELLER_IP" ]; then
      CMD="docker exec -i $NODE curl -X POST http://localhost:5000/disconnect -H 'Content-Type: application/json' -d '{\"seller_ip\": \"$SELLER_IP\"}'"
      echo "🚀 Running: $CMD"
      if [[ "$MODE" == "execute" ]]; then
        eval "$CMD"
      else
        echo
      fi
    else
      echo "⚠️  No IP found for $SELLER_NODE"
    fi
  done

  echo "🔢 $NODE had $COUNT provider connection(s)"
  echo "✅ Done with $NODE"
  echo
  
echo "🔢 Topology had $TOTAL_COUNT provider connection(s)"
done
