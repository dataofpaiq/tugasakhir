#!/usr/bin/env python3
"""
sim_traffic_manual.py

Membuat topologi Mininet sesuai permintaan.
TIDAK otomatis membuka xterm atau menjalankan traffic.
Menyediakan helper scripts di /tmp pada setiap host agar bisa dijalankan manual.

Usage:
    sudo python3 sim_traffic_manual.py

Setelah script jalan kamu akan berada di Mininet CLI. Dari sana:
- Jalankan HTTP server (manual):
    mininet> h4 python3 -m http.server 80 &
    mininet> h7 python3 -m http.server 80 &
- Jalankan client sender (manual):
    mininet> h1 python3 /tmp/send_http_client.py http://10.0.0.4/file1M.bin 0.5  &
    mininet> h5 python3 /tmp/send_http_client.py http://10.0.0.7/file10M.bin 2  &
- Jalankan ping loop (manual):
    mininet> h3 python3 /tmp/ping_loop.py 10.0.0.4 1 &
    mininet> h6 python3 /tmp/ping_loop.py 10.0.0.7 1 &
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
        # switches
        s1 = self.addSwitch('s1', cls=OVSKernelSwitch, protocols='OpenFlow13')
        s2 = self.addSwitch('s2', cls=OVSKernelSwitch, protocols='OpenFlow13')
        s3 = self.addSwitch('s3', cls=OVSKernelSwitch, protocols='OpenFlow13')

        # hosts
        h1 = self.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        h3 = self.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')  # attacker (idle)
        h4 = self.addHost('h4', ip='10.0.0.4/24', mac='00:00:00:00:00:04')  # server
        h5 = self.addHost('h5', ip='10.0.0.5/24', mac='00:00:00:00:00:05')
        h6 = self.addHost('h6', ip='10.0.0.6/24', mac='00:00:00:00:00:06')  # attacker (idle)
        h7 = self.addHost('h7', ip='10.0.0.7/24', mac='00:00:00:00:00:07')  # server

        # links host-switch
        self.addLink(h1, s1)
        self.addLink(h3, s2)
        self.addLink(h4, s2)
        self.addLink(h5, s2)
        self.addLink(h6, s3)
        self.addLink(h7, s3)

        # inter-switch
        self.addLink(s1, s2)
        self.addLink(s2, s3)


def write_helper_scripts(host):
    """
    Writes helper Python scripts into /tmp on the given host (host is a Mininet host object).
    We create:
     - /tmp/send_http_client.py  -> simple wget loop (args: url sleep_seconds)
     - /tmp/ping_loop.py         -> ping loop (args: dest interval_seconds)
    These are NOT executed; user runs them manually via Mininet CLI or xterm.
    """
    send_http = r'''#!/usr/bin/env python3
import sys, time, subprocess

if len(sys.argv) < 3:
    print("Usage: send_http_client.py <url> <sleep_seconds> [count]")
    sys.exit(1)

url = sys.argv[1]
sleep_s = float(sys.argv[2])
count = int(sys.argv[3]) if len(sys.argv) > 3 else 0

i = 0
try:
    while True:
        i += 1
        print(f"[send_http_client] fetching {url} (iter {i})")
        # use wget to be robust in minimal env
        subprocess.run(['wget', '-q', '-O', '/dev/null', url])
        if count and i >= count:
            break
        time.sleep(sleep_s)
except KeyboardInterrupt:
    print("send_http_client stopped by user")
'''
    ping_loop = r'''#!/usr/bin/env python3
import sys, time, subprocess

if len(sys.argv) < 3:
    print("Usage: ping_loop.py <dest_ip> <interval_seconds> [count]")
    sys.exit(1)

dest = sys.argv[1]
interval = float(sys.argv[2])
count = int(sys.argv[3]) if len(sys.argv) > 3 else 0

i = 0
try:
    while True:
        i += 1
        print(f"[ping_loop] pinging {dest} (iter {i})")
        subprocess.run(['ping', '-c', '1', dest])
        if count and i >= count:
            break
        time.sleep(interval)
except KeyboardInterrupt:
    print("ping_loop stopped by user")
'''

    # write to host /tmp
    host.cmd('mkdir -p /tmp')
    host.cmd('bash -c "cat > /tmp/send_http_client.py <<\'PY\'\n' + send_http + '\nPY\n"')
    host.cmd('bash -c "cat > /tmp/ping_loop.py <<\'PY\'\n' + ping_loop + '\nPY\n"')
    host.cmd('chmod +x /tmp/send_http_client.py /tmp/ping_loop.py')


def startNetwork():
    setLogLevel('info')
    topo = MyTopo()
    # remote controller (ONOS) at localhost:6653
    c0 = RemoteController('c0', ip='127.0.0.1', port=6653)
    net = Mininet(topo=topo, controller=c0, link=TCLink, autoSetMacs=True)

    info('*** Starting network\n')
    net.start()
    time.sleep(1)

    # grab hosts
    h1 = net.get('h1')
    h3 = net.get('h3')
    h4 = net.get('h4')
    h5 = net.get('h5')
    h6 = net.get('h6')
    h7 = net.get('h7')

    info('*** Creating sample files on servers (h4,h7) in /tmp/www\n')
    h4.cmd('mkdir -p /tmp/www')
    h7.cmd('mkdir -p /tmp/www')
    # create sample files (do not start servers)
    h4.cmd('dd if=/dev/zero of=/tmp/www/file1M.bin bs=1M count=1 >/dev/null 2>&1 || true')
    h4.cmd('dd if=/dev/zero of=/tmp/www/file5M.bin bs=1M count=5 >/dev/null 2>&1 || true')
    h7.cmd('dd if=/dev/zero of=/tmp/www/file1M.bin bs=1M count=1 >/dev/null 2>&1 || true')
    h7.cmd('dd if=/dev/zero of=/tmp/www/file10M.bin bs=1M count=10 >/dev/null 2>&1 || true')

    info('*** Installing helper scripts on hosts (in /tmp). They are NOT started automatically.\n')
    for host in (h1, h3, h4, h5, h6, h7):
        write_helper_scripts(host)

    info('*** Setup done. Below are manual commands you can run from Mininet CLI or xterm.\n')
    info('Manual server start examples (run in Mininet CLI or xterm inside host):\n')
    info('  # start HTTP servers (in background):\n')
    info('  h4 python3 -m http.server 80 &\n')
    info('  h7 python3 -m http.server 80 &\n')
    info('Manual client start examples (run in Mininet CLI or xterm inside host):\n')
    info('  # run HTTP client (uses wget internally):\n')
    info('  h1 python3 /tmp/send_http_client.py http://10.0.0.4/file1M.bin 0.5 &\n')
    info('  h5 python3 /tmp/send_http_client.py http://10.0.0.7/file10M.bin 2 &\n')
    info('  # run ICMP ping loops:\n')
    info('  h3 python3 /tmp/ping_loop.py 10.0.0.4 1 &\n')
    info('  h6 python3 /tmp/ping_loop.py 10.0.0.7 1 &\n')

    info('*** You can also open an xterm manually for any host (if X available):\n')
    info('  xterm -T h1 -e "sudo mnexec -a $(pgrep -f \'mininet: h1\') -- bash" &\n')
    info('  or from Mininet CLI: xterm h1\n')

    info('*** Entering Mininet CLI. Run manual commands above when ready.\n')
    CLI(net)

    info('*** Stopping network and cleanup\n')
    net.stop()


if __name__ == "__main__":
    startNetwork()
