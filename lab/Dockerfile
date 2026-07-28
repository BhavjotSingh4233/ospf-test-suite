# frr-ospf-lab: an FRRouting image with SSH baked in, for a disposable
# local OSPF test lab. Everything needed to answer "is this router up and
# does it speak OSPF" over SSH is done at *build* time here, rather than
# configured live after `docker run` - that removes an entire class of
# CI flakiness (races between "container started" and "container finished
# being configured").
#
# NOTE: this image is for a throwaway, non-production test lab only. The
# root password below is intentionally simple and intentionally public
# (it's committed to a public GitHub repo) - see README for details. Do
# not reuse this image or password for anything real.
FROM frrouting/frr:latest

ARG ROUTER_ROOT_PASSWORD=frrtest123

# --- SSH -----------------------------------------------------------------
# Alpine's openssh package ships sane non-default defaults already
# (UsePAM no, etc). We only need to flip the two settings required for a
# password-based root login test lab, generate host keys, and set the
# password.
RUN apk add --no-cache openssh \
    && ssh-keygen -A \
    && echo "root:${ROUTER_ROOT_PASSWORD}" | chpasswd \
    && sed -i \
        -e 's/^#\?PermitRootLogin.*/PermitRootLogin yes/' \
        -e 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' \
        /etc/ssh/sshd_config \
    && mkdir -p /run/sshd

# --- OSPF config, baked in --------------------------------------------
# The stock image ships with ospfd=no in /etc/frr/daemons - ospfd simply
# never starts unless that's flipped to yes. `daemons` here is the stock
# file with that one line changed.
#
# See frr.conf for why one file works for all 3 routers unmodified.
# frrcommon.sh (the base image's daemon-startup logic) auto-detects this
# file and applies it via `vtysh -b` on boot - no live vtysh commands
# needed after the container starts.
COPY daemons /etc/frr/daemons
COPY frr.conf /etc/frr/frr.conf
RUN chown frr:frr /etc/frr/daemons /etc/frr/frr.conf \
    && chmod 0644 /etc/frr/daemons \
    && chmod 0600 /etc/frr/frr.conf

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 22

ENTRYPOINT ["/sbin/tini", "--", "/usr/local/bin/entrypoint.sh"]
