# ospf-test-suite

[![OSPF lab CI](https://github.com/BhavjotSingh4233/ospf-test-suite/actions/workflows/ci.yml/badge.svg)](https://github.com/BhavjotSingh4233/ospf-test-suite/actions/workflows/ci.yml)

Automated OSPF neighbor adjacency test suite for a small FRRouting lab -
built, torn down, and rebuilt from scratch by CI on every push, not just
run against a hand-configured environment.

The lab consists of 3 Docker containers running FRRouting, each acting as a
virtual router on a shared subnet (`router-net`, 172.20.0.0/24) and running
OSPF. `test_ospf.py` SSHes into each router (via `netmiko`) and verifies
that OSPF has formed the expected number of full neighbor adjacencies, then
runs a failover/recovery test: it disconnects one router from `router-net`,
confirms the remaining routers notice, reconnects it, and confirms OSPF
reconverges on its own.

## Status

Complete: neighbor adjacency test, failover/recovery test, a
`frr-ospf-lab` Docker image with SSH + OSPF baked in at build time (see
`lab/`), a one-command rebuild script (`setup_lab.sh`), and GitHub
Actions CI that rebuilds the whole lab from a blank runner and runs the
real test suite against it on every push.

## Requirements

- Docker
- Python 3, `netmiko` (`pip install netmiko`)

## Usage

```bash
./setup_lab.sh       # builds the frr-ospf-lab image, creates router-net,
                      # starts router1/2/3, waits for OSPF to converge
python3 test_ospf.py
```

`setup_lab.sh` is non-interactive and idempotent - it tears down any
previous router1/2/3 containers and router-net network first, so it
always produces a clean lab. It's what CI runs, and it's also the
supported way to (re)build the lab locally.

## How the lab is built

`lab/Dockerfile` builds a `frrouting/frr:latest`-based image with SSH and
the OSPF config baked in at *image build* time (`lab/frr.conf`,
`lab/daemons`), rather than configuring each container live after it
starts. That was a deliberate choice for CI reliability: no interactive
`vtysh` replay, no race between "container started" and "container
finished being configured" - by the time a container is running, it's
already fully configured.

## Security note

The lab's root SSH password (`frrtest123`) is intentionally hardcoded
and intentionally committed to this public repo. This is a disposable,
network-isolated test container with no real data or external exposure
(published only to `localhost`, torn down/rebuilt on every CI run) - not
a credential meant to protect anything. Don't reuse this password, or
this image, for anything that isn't a throwaway lab.
