# nokia-ospf-test-suite

Automated OSPF neighbor adjacency test suite for a small FRRouting lab.

The lab consists of 3 Docker containers running FRRouting, each acting as a
virtual router on a shared subnet and running OSPF. This project SSHes into
each router (via `netmiko`) and verifies that OSPF has formed the expected
number of full neighbor adjacencies, reporting a PASS/FAIL result per router.

## Status

Work in progress. Currently scaffolding the connection layer before adding
the neighbor-check and reporting logic.

## Requirements

- Python 3
- `netmiko`
- 3 reachable FRRouting router containers (SSH)

## Usage

```bash
export ROUTER_SSH_PASSWORD=<lab router password>
python3 test_ospf.py
```
