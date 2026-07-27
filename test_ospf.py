"""
OSPF Neighbor Test Suite
------------------------
Connects to each FRRouting router over SSH and verifies that OSPF has
formed the expected number of full neighbor adjacencies.

This is a small automated version of a network regression test:
instead of manually running `show ip ospf neighbor` on each router,
this script does it for all of them and reports PASS/FAIL.

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

# With 3 routers all on one shared subnet, each router should see the
# other 2 as full neighbors.
EXPECTED_NEIGHBOR_COUNT = 2


def get_ospf_neighbor_output(router):
    """SSH into a router and run the OSPF neighbor check via vtysh."""
    connection = ConnectHandler(**{k: v for k, v in router.items() if k != "name"})
    output = connection.send_command("vtysh -c 'show ip ospf neighbor'")
    connection.disconnect()
    return output


def count_full_neighbors(vtysh_output):
    """Count how many neighbor lines show a 'Full' state."""
    full_count = 0
    for line in vtysh_output.splitlines():
        if "Full" in line:
            full_count += 1
    return full_count


def run_tests():
    results = []

    for router in ROUTERS:
        name = router["name"]
        try:
            output = get_ospf_neighbor_output(router)
            full_neighbors = count_full_neighbors(output)
            passed = full_neighbors == EXPECTED_NEIGHBOR_COUNT

            results.append({
                "router": name,
                "passed": passed,
                "full_neighbors": full_neighbors,
                "expected": EXPECTED_NEIGHBOR_COUNT,
                "error": None,
            })
        except Exception as e:
            results.append({
                "router": name,
                "passed": False,
                "full_neighbors": None,
                "expected": EXPECTED_NEIGHBOR_COUNT,
                "error": str(e),
            })

    return results


def print_report(results):
    print("\n=== OSPF Neighbor Test Report ===\n")
    all_passed = True

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        if not r["passed"]:
            all_passed = False

        if r["error"]:
            print(f"[{status}] {r['router']}: ERROR - {r['error']}")
        else:
            print(
                f"[{status}] {r['router']}: "
                f"{r['full_neighbors']} full neighbor(s) "
                f"(expected {r['expected']})"
            )

    print("\n----------------------------------")
    print("OVERALL:", "PASS" if all_passed else "FAIL")
    print("----------------------------------\n")

    return all_passed


if __name__ == "__main__":
    results = run_tests()
    overall_passed = print_report(results)
    exit(0 if overall_passed else 1)
