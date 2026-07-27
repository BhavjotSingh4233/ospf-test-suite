# ospf-test-suite

Automated OSPF neighbor adjacency test suite for a small FRRouting lab.

The lab consists of 3 Docker containers running FRRouting, each acting as a
virtual router on a shared subnet and running OSPF. This project SSHes into
each router (via `netmiko`) and verifies that OSPF has formed the expected
number of full neighbor adjacencies, reporting a PASS/FAIL result per router.

## Status

Core OSPF neighbor adjacency test is complete: connects to all 3 routers,
checks full neighbor counts, and prints a PASS/FAIL report per router plus
an overall result.

Planned next: a failover test that drops a router and confirms the
remaining two reconverge.

## Requirements

- Python 3
- `netmiko`
- 3 reachable FRRouting router containers (SSH)

## Usage

```bash
export ROUTER_SSH_PASSWORD=<lab router password>
python3 test_ospf.py
```
