"""
OSPF Neighbor Test Suite
------------------------
Connects to each FRRouting router over SSH and verifies that OSPF has
formed the expected number of full neighbor adjacencies.

This is a small automated version of a network regression test:
instead of manually running `show ip ospf neighbor` on each router,
this script does it for all of them and reports PASS/FAIL.

Status: connection logic only. Pass/fail checking and reporting are
added in a later commit.
"""

import os

from netmiko import ConnectHandler

# --- Router inventory -------------------------------------------------
# Each router is reachable on localhost, on the SSH port we published
# when we recreated its container (2201, 2202, 2203).
ROUTER_PASSWORD = os.environ.get("ROUTER_SSH_PASSWORD", "changeme")

ROUTERS = [
    {
        "device_type": "linux",
        "host": "localhost",
        "username": "root",
        "password": ROUTER_PASSWORD,
        "port": 2201,
        "name": "router1",
        "use_keys": False,
        "allow_agent": False,
    },
    {
        "device_type": "linux",
        "host": "localhost",
        "username": "root",
        "password": ROUTER_PASSWORD,
        "port": 2202,
        "name": "router2",
        "use_keys": False,
        "allow_agent": False,
    },
    {
        "device_type": "linux",
        "host": "localhost",
        "username": "root",
        "password": ROUTER_PASSWORD,
        "port": 2203,
        "name": "router3",
        "use_keys": False,
        "allow_agent": False,
    },
]


def get_ospf_neighbor_output(router):
    """SSH into a router and run the OSPF neighbor check via vtysh."""
    connection = ConnectHandler(**{k: v for k, v in router.items() if k != "name"})
    output = connection.send_command("vtysh -c 'show ip ospf neighbor'")
    connection.disconnect()
    return output


if __name__ == "__main__":
    for router in ROUTERS:
        print(f"--- {router['name']} ---")
        print(get_ospf_neighbor_output(router))
