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
import shutil
import subprocess
import time

from netmiko import ConnectHandler

# --- Router inventory -------------------------------------------------
# Each router is reachable over SSH on the port we published for its
# container (2201/2202/2203). The host defaults to "localhost" because
# that resolves correctly both on a Mac running Docker Desktop and on a
# GitHub Actions runner (Docker runs directly on the runner VM there, not
# nested inside another container, so published ports are reachable the
# same way). ROUTER_SSH_HOST/ROUTER_SSH_PASSWORD are still overridable in
# case that ever changes.
ROUTER_SSH_HOST = os.environ.get("ROUTER_SSH_HOST", "localhost")
ROUTER_SSH_PASSWORD = os.environ.get("ROUTER_SSH_PASSWORD", "frrtest123")

ROUTERS = [
    {
        "device_type": "linux",
        "host": ROUTER_SSH_HOST,
        "username": "root",
        "password": ROUTER_SSH_PASSWORD,
        "port": 2201,
        "name": "router1",
        "use_keys": False,
        "allow_agent": False,
    },
    {
        "device_type": "linux",
        "host": ROUTER_SSH_HOST,
        "username": "root",
        "password": ROUTER_SSH_PASSWORD,
        "port": 2202,
        "name": "router2",
        "use_keys": False,
        "allow_agent": False,
    },
    {
        "device_type": "linux",
        "host": ROUTER_SSH_HOST,
        "username": "root",
        "password": ROUTER_SSH_PASSWORD,
        "port": 2203,
        "name": "router3",
        "use_keys": False,
        "allow_agent": False,
    },
]

# With 3 routers all on one shared subnet, each router should see the
# other 2 as full neighbors.
EXPECTED_NEIGHBOR_COUNT = 2

# --- Failover test configuration --------------------------------------
DOCKER_NETWORK = "router-net"
OBSERVER_ROUTER = "router1"   # the router we watch while router3 goes down
FAILOVER_ROUTER = "router3"   # the router we disconnect/reconnect

# Resolve the docker binary via PATH first (this is what works on a
# GitHub Actions runner and most Linux boxes), then fall back to the
# common locations Docker Desktop uses on macOS, since a shell started
# from a GUI app (e.g. IDLE) doesn't always inherit Terminal's PATH. Can
# also be forced with the DOCKER_BIN env var.
def _find_docker_bin():
    env_override = os.environ.get("DOCKER_BIN")
    if env_override:
        return env_override

    found = shutil.which("docker")
    if found:
        return found

    for candidate in ("/usr/local/bin/docker", "/opt/homebrew/bin/docker", "/usr/bin/docker"):
        if os.path.exists(candidate):
            return candidate

    raise RuntimeError(
        "Could not locate the docker binary. Set the DOCKER_BIN environment "
        "variable to its full path."
    )


DOCKER_BIN = _find_docker_bin()

# OSPF's default "dead interval" is 40 seconds - a neighbor isn't
# declared down until that long has passed with no hello received. CI
# runners can be noticeably slower/jittery than a local machine, so
# rather than a single blind sleep-then-check (which either wastes time
# or, worse, checks too early and fails a slow-but-healthy run), these
# poll for the expected state and give up only after a generous timeout.
# All are overridable via env vars for a slower CI runner.
INITIAL_CONVERGENCE_TIMEOUT_SECONDS = int(os.environ.get("INITIAL_CONVERGENCE_TIMEOUT_SECONDS", 90))
FAILURE_DETECTION_TIMEOUT_SECONDS = int(os.environ.get("FAILURE_DETECTION_TIMEOUT_SECONDS", 75))
RECOVERY_TIMEOUT_SECONDS = int(os.environ.get("RECOVERY_TIMEOUT_SECONDS", 60))
POLL_INTERVAL_SECONDS = 3


def get_ospf_neighbor_output(router, connect_retries=3, retry_delay_seconds=3):
    """SSH into a router and run the OSPF neighbor check via vtysh.

    A container that was just (re)started may take a moment for sshd to
    start accepting connections, especially on a loaded CI runner, so a
    fresh SSH connection gets a couple of quick retries before giving up.
    """
    connect_kwargs = {k: v for k, v in router.items() if k != "name"}

    last_error = None
    for attempt in range(connect_retries):
        try:
            connection = ConnectHandler(**connect_kwargs)
            output = connection.send_command("vtysh -c 'show ip ospf neighbor'")
            connection.disconnect()
            return output
        except Exception as e:
            last_error = e
            if attempt < connect_retries - 1:
                time.sleep(retry_delay_seconds)

    raise last_error


def count_full_neighbors(vtysh_output):
    """Count how many neighbor lines show a 'Full' state."""
    full_count = 0
    for line in vtysh_output.splitlines():
        if "Full" in line:
            full_count += 1
    return full_count


def wait_for_full_neighbor_count(router, expected_count, timeout_seconds):
    """Poll a router until it reports the expected full-neighbor count.

    Returns (output, count) for the last check performed - either the
    first one that matched, or the final one before timing out. Polling
    instead of a single blind sleep-then-check means a fast-converging
    local run isn't slowed down, and a slow-converging CI run isn't
    failed just for needing a few extra seconds.
    """
    deadline = time.time() + timeout_seconds
    output = ""
    count = -1

    while True:
        output = get_ospf_neighbor_output(router)
        count = count_full_neighbors(output)
        if count == expected_count or time.time() >= deadline:
            return output, count
        time.sleep(POLL_INTERVAL_SECONDS)


def get_router_by_name(name):
    """Look up a router's connection info from ROUTERS by its name."""
    for router in ROUTERS:
        if router["name"] == name:
            return router
    raise ValueError(f"No router named {name} in ROUTERS")


def docker_network_disconnect(container_name):
    """Simulate a link failure by unplugging a container from the network."""
    subprocess.run(
        [DOCKER_BIN, "network", "disconnect", DOCKER_NETWORK, container_name],
        check=True,
        capture_output=True,
    )


def docker_network_connect(container_name):
    """Simulate the link coming back by reconnecting the container."""
    subprocess.run(
        [DOCKER_BIN, "network", "connect", DOCKER_NETWORK, container_name],
        check=True,
        capture_output=True,
    )


def run_failover_test():
    """
    Resilience test: disconnect one router from the network, confirm the
    remaining routers notice (neighbor count drops), then reconnect it and
    confirm OSPF automatically recovers (neighbor count returns to normal).

    This test uses `docker network disconnect/connect` directly (via
    subprocess) rather than SSH/netmiko, since it's simulating a physical
    link failure - not something you'd do from inside the router itself.
    """
    observer = get_router_by_name(OBSERVER_ROUTER)
    steps = []

    try:
        # Step 1: baseline - confirm we start fully adjacent. Uses the
        # same poll-with-timeout helper as the other steps in case this
        # runs immediately after the lab comes up and OSPF hasn't quite
        # finished converging yet.
        baseline_output, baseline_count = wait_for_full_neighbor_count(
            observer, EXPECTED_NEIGHBOR_COUNT, INITIAL_CONVERGENCE_TIMEOUT_SECONDS
        )
        steps.append(("baseline", baseline_count, EXPECTED_NEIGHBOR_COUNT))

        # Step 2: simulate the link going down, then poll (rather than a
        # blind sleep) until the neighbor count drops or we time out.
        docker_network_disconnect(FAILOVER_ROUTER)
        expected_down_count = EXPECTED_NEIGHBOR_COUNT - 1
        down_output, down_count = wait_for_full_neighbor_count(
            observer, expected_down_count, FAILURE_DETECTION_TIMEOUT_SECONDS
        )
        steps.append(("failure_detected", down_count, expected_down_count))

        # Step 3: bring the link back, then poll until OSPF re-converges.
        docker_network_connect(FAILOVER_ROUTER)
        recovered_output, recovered_count = wait_for_full_neighbor_count(
            observer, EXPECTED_NEIGHBOR_COUNT, RECOVERY_TIMEOUT_SECONDS
        )
        steps.append(("recovery", recovered_count, EXPECTED_NEIGHBOR_COUNT))

        passed = all(actual == expected for _, actual, expected in steps)

        return {
            "test": "failover_and_recovery",
            "passed": passed,
            "steps": steps,
            "error": None,
        }

    except Exception as e:
        # Safety net: always try to reconnect the router, even if a step
        # above failed, so a failed test run doesn't leave the lab broken.
        try:
            docker_network_connect(FAILOVER_ROUTER)
        except Exception:
            pass

        return {
            "test": "failover_and_recovery",
            "passed": False,
            "steps": steps,
            "error": str(e),
        }


def print_failover_report(result):
    print("=== Failover & Recovery Test ===\n")
    labels = {
        "baseline": "Baseline (all routers up)",
        "failure_detected": "After disconnecting router3",
        "recovery": "After reconnecting router3",
    }

    if result["error"]:
        print(f"[FAIL] {result['test']}: ERROR - {result['error']}")
    else:
        for step_name, actual, expected in result["steps"]:
            status = "PASS" if actual == expected else "FAIL"
            label = labels.get(step_name, step_name)
            print(f"[{status}] {label}: {actual} full neighbor(s) (expected {expected})")

    print("\n----------------------------------")
    print("FAILOVER TEST:", "PASS" if result["passed"] else "FAIL")
    print("----------------------------------\n")


def run_tests():
    results = []

    for router in ROUTERS:
        name = router["name"]
        try:
            # Polls rather than checking once, so a run started right
            # after the lab comes up (e.g. in CI) doesn't fail just
            # because OSPF hasn't finished converging in the first
            # instant.
            output, full_neighbors = wait_for_full_neighbor_count(
                router, EXPECTED_NEIGHBOR_COUNT, INITIAL_CONVERGENCE_TIMEOUT_SECONDS
            )
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
    neighbor_tests_passed = print_report(results)

    failover_result = run_failover_test()
    print_failover_report(failover_result)

    overall_passed = neighbor_tests_passed and failover_result["passed"]
    exit(0 if overall_passed else 1)
