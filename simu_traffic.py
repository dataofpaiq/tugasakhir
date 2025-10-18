#!/usr/bin/env python3
"""
sim_traffic.py

Mininet script: buka xterm per-host dengan TITLE = nama host (h1, h3, h4, ...)
Simulasi trafik normal (HTTP download loops + ICMP pings).
Jalankan:
    sudo python3 sim_traffic.py
"""

from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.term import makeTerm
import time
import os

class MyTopo(Topo):
    def build(self):
        # Tambah 3 switch
        s1 = self.addSwitch('s1', cls=OVSKernelSwitch, protocols='OpenFlow13')
        s2 = self.addSwitch('s2', cls=OVSKernelSwitch, protocols='OpenFlow13')
        s3 = self.addSwitch('s3', cls=OVSKernelSwitch, protocols='OpenFlow13')

        # Tambah 6 host (sesuai inputmu)
        h1 = self.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        h3 = self.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03') # Attacker (idle)
        h4 = self.addHost('h4', ip='10.0.0.4/24', mac='00:00:00:00:00:04') # server
        h5 = self.addHost('h5', ip='10.0.0.5/24', mac='00:00:00:00:00:05')
        h6 = self.addHost('h6', ip='10.0.0.6/24', mac='00:00:00:00:00:06') # Attacker (idle)
        h7 = self.addHost('h7', ip='10.0.0.7/24', mac='00:00:00:00:00:07') # server

        # Sambungkan host ke switch
        self.addLink(h1, s1)
        self.addLink(h3, s2)
        self.addLink(h4, s2)
        self.addLink(h5, s2)
        self.addLink(h6, s3)
        self.addLink(h7, s3)

        # Interkoneksi antar switch
        self.addLink(s1, s2)
        self.addLink(s2, s3)


def startNetwork():
    setLogLevel('info')
    topo = MyTopo()
    c0 = RemoteController('c0', ip='127.0.0.1', port=6653)
    net = Mininet(topo=topo, controller=c0, link=TCLink, autoSetMacs=True)

    info('*** Starting network\n')
    net.start()
    time.sleep(2)

    # Ambil objek host
    h1 = net.get('h1')
    h3 = net.get('h3')
    h4 = net.get('h4')
    h5 = net.get('h5')
    h6 = net.get('h6')
    h7 = net.get('h7')

    info('*** Membuat file sample di server (h4, h7)\n')
    # Pastikan direktori /tmp/www ada dan buat file ukuran berbeda
    h4.cmd('mkdir -p /tmp/www')
    h7.cmd('mkdir -p /tmp/www')
    h4.cmd('dd if=/dev/zero of=/tmp/www/file1M.bin bs=1M count=1 >/dev/null 2>&1 || true')
    h4.cmd('dd if=/dev/zero of=/tmp/www/file5M.bin bs=1M count=5 >/dev/null 2>&1 || true')
    h7.cmd('dd if=/dev/zero of=/tmp/www/file1M.bin bs=1M count=1 >/dev/null 2>&1 || true')
    h7.cmd('dd if=/dev/zero of=/tmp/www/file10M.bin bs=1M count=10 >/dev/null 2>&1 || true')

    info('*** Menjalankan HTTP server di h4 dan h7 (xterm dengan title host)\n')
    # gunakan title = host.name agar xterm mudah dikenali
    makeTerm(h4, cmd='bash -ic "cd /tmp/www && python3 -m http.server 80 2>&1 | tee /tmp/h4_http.log"', title=h4.name)
    makeTerm(h7, cmd='bash -ic "cd /tmp/www && python3 -m http.server 80 2>&1 | tee /tmp/h7_http.log"', title=h7.name)
    time.sleep(1)

    info('*** Men-start traffic generators di xterm untuk clients (h1,h5) dengan TITLE host\n')
    # h1: loop wget ke h4 (file1M + file5M) bergantian
    cmd_h1 = (
        'bash -ic "'
        'while true; do '
        'echo \"[h1] wget file1M from h4\"; wget -q -O /dev/null http://10.0.0.4/file1M.bin; sleep 0.5; '
        'echo \"[h1] wget file5M from h4\"; wget -q -O /dev/null http://10.0.0.4/file5M.bin; sleep 1; '
        'done"'
    )
    makeTerm(h1, cmd=cmd_h1, title=h1.name)

    # h5: loop wget ke h7 (file1M + file10M)
    cmd_h5 = (
        'bash -ic "'
        'while true; do '
        'echo \"[h5] wget file1M from h7\"; wget -q -O /dev/null http://10.0.0.7/file1M.bin; sleep 0.6; '
        'echo \"[h5] wget file10M from h7\"; wget -q -O /dev/null http://10.0.0.7/file10M.bin; sleep 2; '
        'done"'
    )
    makeTerm(h5, cmd=cmd_h5, title=h5.name)

    info('*** Menjalankan ping background di beberapa host untuk ICMP traffic (xterm dengan title host)\n')
    makeTerm(h3, cmd='bash -ic "while true; do ping -c1 10.0.0.4; sleep 1; done"', title=h3.name)
    makeTerm(h6, cmd='bash -ic "while true; do ping -c1 10.0.0.7; sleep 1; done"', title=h6.name)

    info('*** Semua xterm terbuka (title = nama host). Masuk ke Mininet CLI untuk kontrol manual.\n')
    info(' - Lihat log http server: /tmp/h4_http.log di h4 xterm, /tmp/h7_http.log di h7 xterm\n')
    info(' - Jika mau hentikan simulasi, tutup xterm atau gunakan Mininet CLI "exit" lalu net.stop()\n')

    CLI(net)

    info('*** Stopping network\n')
    net.stop()
    # clean up any lingering xterms (best-effort)
    os.system("pkill -f xterm || true")


if __name__ == '__main__':
    startNetwork()
