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

## Architecture

```
                 router-net  (172.20.0.0/24)

        router1 -------------------- router2
       172.20.0.2                  172.20.0.3
            \                          /
             \                        /
              \                      /
                     router3
                   172.20.0.4

  All 3 containers run FRRouting + OSPF, and are fully meshed
  on one shared Docker network - each sees the other two as
  direct OSPF neighbors.

  test_ospf.py (netmiko/SSH) --> router1:2201
                              --> router2:2202
                              --> router3:2203
```

Each router is a container built from the custom `frr-ospf-lab` image
(see `lab/`), with SSH and OSPF configuration baked in at build time
rather than configured live after the container starts.

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

## Sample output

```
=== OSPF Neighbor Test Report ===

[PASS] router1: 2 full neighbor(s) (expected 2)
[PASS] router2: 2 full neighbor(s) (expected 2)
[PASS] router3: 2 full neighbor(s) (expected 2)

----------------------------------
OVERALL: PASS
----------------------------------

=== Failover & Recovery Test ===

[PASS] Baseline (all routers up): 2 full neighbor(s) (expected 2)
[PASS] After disconnecting router3: 1 full neighbor(s) (expected 1)
[PASS] After reconnecting router3: 2 full neighbor(s) (expected 2)

----------------------------------
FAILOVER TEST: PASS
----------------------------------
```

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

## Next steps

- Parameterize the topology (currently fixed at 3 routers) so the lab
  can be resized without editing `setup_lab.sh` directly.
- Generate a random SSH password per run instead of the hardcoded one,
  passed via `docker build --build-arg` and `ROUTER_SSH_PASSWORD`, so
  nothing sensitive-looking sits in git even though it's low-risk here.
- Add a second routing protocol (e.g. BGP) to compare convergence and
  failover behavior against OSPF.
