#!/bin/bash
# Custom entrypoint for the frr-ospf-lab image.
#
# The stock frrouting/frr image's entrypoint (/usr/lib/frr/docker-start)
# only starts the FRR daemons (zebra/ospfd/staticd via watchfrr) - it knows
# nothing about SSH. We start sshd first (it daemonizes itself, i.e. forks
# and returns immediately), then exec into the original entrypoint so FRR's
# startup/log behavior is unchanged and PID 1 duties stay with tini either
# way.
set -euo pipefail

mkdir -p /run/sshd
/usr/sbin/sshd

exec /usr/lib/frr/docker-start
