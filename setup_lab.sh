#!/usr/bin/env bash
# Rebuilds the 3-router FRR/OSPF lab from a completely blank Docker
# environment: pulls the base FRR image, builds the frr-ospf-lab image
# (SSH + OSPF config baked in at build time - see lab/Dockerfile and
# lab/frr.conf), creates router-net, launches router1/2/3 on it with
# their SSH ports published, and waits for OSPF to fully converge before
# returning.
#
# Non-interactive and idempotent: safe to run on a machine that has
# never seen Docker before, and safe to re-run on one that already has a
# lab up (any existing router1/2/3 containers and router-net network from
# a previous run are torn down first, so this always produces a fresh
# lab). Used both for local rebuilds (`./setup_lab.sh`) and by CI
# (.github/workflows/ci.yml).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAB_DIR="$SCRIPT_DIR/lab"

IMAGE_NAME="frr-ospf-lab:latest"
NETWORK_NAME="router-net"
NETWORK_SUBNET="172.20.0.0/24"
ROUTER_NAMES=(router1 router2 router3)
ROUTER_PORTS=(2201 2202 2203)
EXPECTED_FULL_NEIGHBORS=2

# How long to wait for OSPF to fully converge across all 3 routers before
# giving up. CI runners are typically slower/noisier than a local
# machine, so this defaults higher than what's actually needed locally
# (convergence normally finishes in well under a minute). Override with
# the env var if needed.
CONVERGENCE_TIMEOUT_SECONDS="${CONVERGENCE_TIMEOUT_SECONDS:-150}"
SSH_READY_TIMEOUT_SECONDS="${SSH_READY_TIMEOUT_SECONDS:-30}"

log() {
    echo "[setup_lab] $*"
}

log "Pulling base image frrouting/frr:latest..."
docker pull frrouting/frr:latest

log "Removing any previous lab containers and network..."
for name in "${ROUTER_NAMES[@]}"; do
    docker rm -f "$name" >/dev/null 2>&1 || true
done
docker network rm "$NETWORK_NAME" >/dev/null 2>&1 || true

log "Building $IMAGE_NAME from $LAB_DIR..."
docker build -t "$IMAGE_NAME" "$LAB_DIR"

log "Creating network $NETWORK_NAME ($NETWORK_SUBNET)..."
docker network create "$NETWORK_NAME" --subnet "$NETWORK_SUBNET" >/dev/null

# Each router is started with its SSH port published on the default
# bridge network first, THEN connected to router-net. This mirrors what
# actually works for Docker's port-publishing/NAT with a
# multi-network container - publishing the port only at `docker run`
# time (before router-net is attached) is what makes the mapping
# reliable.
for i in "${!ROUTER_NAMES[@]}"; do
    name="${ROUTER_NAMES[$i]}"
    port="${ROUTER_PORTS[$i]}"
    log "Starting $name (SSH will be published on localhost:$port)..."
    docker run -d --privileged --name "$name" -p "${port}:22" "$IMAGE_NAME" >/dev/null
    docker network connect "$NETWORK_NAME" "$name"
done

log "Waiting for sshd to accept connections on each router (up to ${SSH_READY_TIMEOUT_SECONDS}s each)..."
for port in "${ROUTER_PORTS[@]}"; do
    deadline=$((SECONDS + SSH_READY_TIMEOUT_SECONDS))
    until (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; do
        if [ "$SECONDS" -ge "$deadline" ]; then
            log "ERROR: nothing is listening on localhost:$port after ${SSH_READY_TIMEOUT_SECONDS}s"
            exit 1
        fi
        sleep 1
    done
    exec 3<&- 3>&- 2>/dev/null || true
done

log "Waiting for OSPF to fully converge (each router expecting $EXPECTED_FULL_NEIGHBORS full neighbor(s), up to ${CONVERGENCE_TIMEOUT_SECONDS}s total)..."
deadline=$((SECONDS + CONVERGENCE_TIMEOUT_SECONDS))
for name in "${ROUTER_NAMES[@]}"; do
    while true; do
        full_count=$(docker exec "$name" vtysh -c "show ip ospf neighbor" 2>/dev/null | grep -c "Full" || true)
        if [ "$full_count" -ge "$EXPECTED_FULL_NEIGHBORS" ]; then
            log "$name: $full_count full neighbor(s) - OK"
            break
        fi
        if [ "$SECONDS" -ge "$deadline" ]; then
            log "ERROR: $name only has $full_count full neighbor(s) after ${CONVERGENCE_TIMEOUT_SECONDS}s"
            log "Last OSPF neighbor state for $name:"
            docker exec "$name" vtysh -c "show ip ospf neighbor" || true
            exit 1
        fi
        sleep 2
    done
done

log "Lab is up. router1/2/3 are on localhost:${ROUTER_PORTS[0]}/${ROUTER_PORTS[1]}/${ROUTER_PORTS[2]} (root/frrtest123), OSPF fully converged."
