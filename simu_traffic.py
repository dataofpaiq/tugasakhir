#!/usr/bin/env python3
"""
sim_traffic_manual_v2.py

- Run this manually inside an xterm (do NOT let script open xterms automatically).
- It creates the topology, creates sample files and helper *shell* scripts in /tmp on each host.
- It does NOT auto-run traffic. You must start servers/clients manually from Mininet CLI or an xterm.

Usage:
    sudo python3 sim_traffic_manual_v2.py
"""
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info
import time

class MyTopo(Topo):
    def build(self):
        s1 = self.addSwitch('s1', cls=OVSKernelSwitch, protocols='OpenFlow13')
        s2 = self.addSwitch('s2', cls=OVSKernelSwitch, protocols='OpenFlow13')
        s3 = self.addSwitch('s3', cls=OVSKernelSwitch, protocols='OpenFlow13')

        h1 = self.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        h3 = self.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')  # attacker (idle)
        h4 = self.addHost('h4', ip='10.0.0.4/24', mac='00:00:00:00:00:04')  # server
        h5 = self.addHost('h5', ip='10.0.0.5/24', mac='00:00:00:00:00:05')
        h6 = self.addHost('h6', ip='10.0.0.6/24', mac='00:00:00:00:00:06')  # attacker (idle)
        h7 = self.addHost('h7', ip='10.0.0.7/24', mac='00:00:00:00:00:07')  # server

        # connect hosts to switches
        self.addLink(h1, s1)
        self.addLink(h3, s2)
        self.addLink(h4, s2)
        self.addLink(h5, s2)
        self.addLink(h6, s3)
        self.addLink(h7, s3)

        # inter-switch links
        self.addLink(s1, s2)
        self.addLink(s2, s3)


def write_shell_helpers(host):
    """
    Create POSIX shell helpers under /tmp on the given Mininet host.

    - /tmp/send_http_client.sh <url> <sleep_s> [count]
      uses wget to fetch URL repeatedly (quiet), sleeps between iterations.
    - /tmp/ping_loop.sh <dest_ip> <interval_s> [count]
      runs 'ping -c 1' in a loop.

    These are plain shell scripts (no Python heredoc), safe for pingall and shell parsing.
    """
    send_http = r"""#!/bin/sh
# send_http_client.sh <url> <sleep_s> [count]
if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <url> <sleep_seconds> [count]"
  exit 1
fi
URL="$1"
SLEEP="$2"
COUNT=0
if [ "$#" -ge 3 ]; then
  COUNT="$3"
fi
i=0
while :
do
  i=$((i + 1))
  echo "[send_http_client] iter $i fetching $URL"
  wget -q -O /dev/null "$URL"
  if [ "$COUNT" -ne 0 ] && [ "$i" -ge "$COUNT" ]; then
    break
  fi
  sleep "$SLEEP"
done
"""

    ping_loop = r"""#!/bin/sh
# ping_loop.sh <dest_ip> <interval_s> [count]
if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <dest_ip> <interval_seconds> [count]"
  exit 1
fi
DEST="$1"
INTERVAL="$2"
COUNT=0
if [ "$#" -ge 3 ]; then
  COUNT="$3"
fi
i=0
while :
do
  i=$((i + 1))
  echo "[ping_loop] iter $i -> $DEST"
  ping -c 1 "$DEST"
  if [ "$COUNT" -ne 0 ] && [ "$i" -ge "$COUNT" ]; then
    break
  fi
  sleep "$INTERVAL"
done
"""

    # write to host /tmp
    host.cmd('mkdir -p /tmp')
    # use a safe redirect to write the content
    host.cmd('bash -c "cat > /tmp/send_http_client.sh <<\'SH\'\n' + send_http + '\nSH\n"')
    host.cmd('bash -c "cat > /tmp/ping_loop.sh <<\'SH\'\n' + ping_loop + '\nSH\n"')
    host.cmd('chmod +x /tmp/send_http_client.sh /tmp/ping_loop.sh')


def startNetwork():
    setLogLevel('info')
    topo = MyTopo()
    c0 = RemoteController('c0', ip='127.0.0.1', port=6653)
    net = Mininet(topo=topo, controller=c0, link=TCLink, autoSetMacs=True)

    info('*** Starting network\n')
    net.start()
    time.sleep(1)

    # get host objects
    hosts = { name: net.get(name) for name in ('h1','h3','h4','h5','h6','h7') }

    info('*** Creating sample files on servers (h4,h7) under /tmp/www\n')
    hosts['h4'].cmd('mkdir -p /tmp/www')
    hosts['h7'].cmd('mkdir -p /tmp/www')
    hosts['h4'].cmd('dd if=/dev/zero of=/tmp/www/file1M.bin bs=1M count=1 >/dev/null 2>&1 || true')
    hosts['h4'].cmd('dd if=/dev/zero of=/tmp/www/file5M.bin bs=1M count=5 >/dev/null 2>&1 || true')
    hosts['h7'].cmd('dd if=/dev/zero of=/tmp/www/file1M.bin bs=1M count=1 >/dev/null 2>&1 || true')
    hosts['h7'].cmd('dd if=/dev/zero of=/tmp/www/file10M.bin bs=1M count=10 >/dev/null 2>&1 || true')

    info('*** Installing POSIX shell helper scripts on hosts (in /tmp). They are NOT started automatically.\n')
    for h in hosts.values():
        write_shell_helpers(h)

    info('*** Setup finished. IMPORTANT: This script does NOT open xterms or auto-run traffic.\n')
    info('Manual commands you can run from the mininet> prompt or in an xterm (open xterm manually):\n')
    info('  # Start HTTP servers in background (on server hosts):\n')
    info('    h4 python3 -m http.server 80 &\n')
    info('    h7 python3 -m http.server 80 &\n')
    info('  # Run HTTP client loops (manual):\n')
    info('    h1 /tmp/send_http_client.sh http://10.0.0.4/file1M.bin 0.5 &\n')
    info('    h5 /tmp/send_http_client.sh http://10.0.0.7/file10M.bin 2 &\n')
    info('  # Run ping loops (manual):\n')
    info('    h3 /tmp/ping_loop.sh 10.0.0.4 1 &\n')
    info('    h6 /tmp/ping_loop.sh 10.0.0.7 1 &\n')
    info('  # To stop a background job in a host, use: pkill -f send_http_client.sh (or ping_loop.sh) on that host.\n')
    info('\n')
    info('*** Now entering Mininet CLI in this xterm. Run manual commands above when ready.\n')

    CLI(net)

    info('*** Stopping network and cleanup...\n')
    net.stop()


if __name__ == "__main__":
    startNetwork()
