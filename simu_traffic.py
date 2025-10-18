#!/usr/bin/env python3
"""
generate_traffic.py (updated)

Features:
 - start HTTP servers on h4,h7 and clients (h1,h5) + ping loops (h3,h6) in Mininet hosts
 - default mode (run on host OS) uses mnexec to execute per-host commands
 - --auto-stop <seconds> : automatically stop background jobs after N seconds
 - --write-mininet-cmds <file> : write a list of Mininet-CLI commands (hX ...) you can paste
   into the Mininet CLI to start the traffic there (alternative to host-mode)
 - logs are written to /tmp/<host>_*.log inside Mininet hosts

Usage (host OS terminal):
  sudo python3 generate_traffic.py
  sudo python3 generate_traffic.py --auto-stop 60
  sudo python3 generate_traffic.py --write-mininet-cmds start.cmds

Notes:
 - This script assumes your Mininet topology is already running and hosts have names h1,h3,h4,h5,h6,h7.
 - If host names differ, edit the HOST lists (SERVERS/CLIENTS/PINGS) accordingly.
"""

import subprocess, shlex, time, sys, os, argparse

# ------------------------------------------------------------------------------
# Configuration: edit if your host names or IPs differ
# ------------------------------------------------------------------------------
SERVERS = {
    "h4": {
        "www_dir": "/tmp/www",
        "files": [("file1M.bin", 1), ("file5M.bin", 5)],
        "start_cmd": "cd /tmp/www && nohup python3 -m http.server 80 > /tmp/h4_http.log 2>&1 &"
    },
    "h7": {
        "www_dir": "/tmp/www",
        "files": [("file1M.bin", 1), ("file10M.bin", 10)],
        "start_cmd": "cd /tmp/www && nohup python3 -m http.server 80 > /tmp/h7_http.log 2>&1 &"
    },
}

CLIENTS = {
    # host: (url, sleep_seconds, iterations(0=infinite))
    "h1": ("http://10.0.0.4/file1M.bin", 0.7, 0),
    "h5": ("http://10.0.0.7/file10M.bin", 2.0, 0),
}

PINGS = {
    "h3": ("10.0.0.4", 1.0, 0),
    "h6": ("10.0.0.7", 1.0, 0),
}

# Names of the client/ping scripts inside hosts for pkill/cleanup
CLIENT_SCRIPT_NAME = "/tmp/send_http_client.sh"
PING_SCRIPT_NAME = "/tmp/ping_loop.sh"

# ------------------------------------------------------------------------------
# Helpers for running shell commands on the host OS
# ------------------------------------------------------------------------------
def run_local(cmd):
    """Run command in host OS shell. Return (rc, stdout, stderr)."""
    try:
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        return p.returncode, out.decode(errors='ignore'), err.decode(errors='ignore')
    except Exception as e:
        return 1, "", str(e)

def find_host_pid(hostname):
    """Return the PID for the Mininet host process 'mininet: <hostname>' (first match) or None."""
    rc, out, err = run_local(f"pgrep -f 'mininet: {hostname}'")
    if rc != 0 or not out.strip():
        return None
    return out.strip().splitlines()[0].strip()

def mnexec_run(pid, cmdline):
    """Execute a command inside Mininet host namespace using mnexec -a <pid> -- sh -c '<cmdline>'.
       Returns (rc, out, err)."""
    full = f"sudo mnexec -a {pid} -- sh -c {shlex.quote(cmdline)}"
    return run_local(full)

# ------------------------------------------------------------------------------
# Construct mininet-CLI commands (text) so user can paste them into Mininet prompt
# ------------------------------------------------------------------------------
def build_mininet_commands():
    """Return lines (list of str) of Mininet CLI commands to start servers/clients/pings."""
    lines = []
    # server start commands
    for h, conf in SERVERS.items():
        # create files
        lines.append(f"{h} mkdir -p {conf['www_dir']}")
        for fname, mb in conf['files']:
            lines.append(f"{h} dd if=/dev/zero of={conf['www_dir']}/{fname} bs=1M count={mb}")
        # start http server
        lines.append(f"{h} python3 -m http.server 80 > /tmp/{h}_http.log 2>&1 &")
    # client commands
    for host, (url, sleep_s, iters) in CLIENTS.items():
        lines.append(f"{host} {CLIENT_SCRIPT_NAME} \"{url}\" {sleep_s} {iters} &")
    # ping scripts
    for host, (dest, interval, iters) in PINGS.items():
        lines.append(f"{host} {PING_SCRIPT_NAME} {dest} {interval} {iters} &")
    # convenience: logfile tails
    lines.append("# tail logs examples: h1 tail -f /tmp/h1_client.log")
    return lines

# ------------------------------------------------------------------------------
# Functions to install and start jobs via mnexec
# ------------------------------------------------------------------------------
def ensure_server_files(pid, server_conf, host):
    cmds = [f"mkdir -p {server_conf['www_dir']}"]
    for fname, mb in server_conf['files']:
        cmds.append(f"dd if=/dev/zero of={server_conf['www_dir']}/{fname} bs=1M count={mb} >/dev/null 2>&1 || true")
    rc, out, err = mnexec_run(pid, " && ".join(cmds))
    return rc == 0

def start_server(pid, server_conf, host):
    rc, out, err = mnexec_run(pid, server_conf['start_cmd'])
    return rc == 0

def start_client(pid, url, sleep_s, iterations, host):
    # write script to /tmp/send_http_client.sh inside host and run it
    script = f"""cat > {CLIENT_SCRIPT_NAME} <<'SH'
#!/bin/sh
URL="{url}"
SLEEP="{sleep_s}"
COUNT={int(iterations)}
i=0
while :
do
  i=$((i+1))
  echo "[send_http_client] iter $i fetching $URL" >> /tmp/{host}_generate.log 2>&1
  wget -q -O /dev/null "$URL"
  if [ "$COUNT" -ne 0 ] && [ "$i" -ge "$COUNT" ]; then
    break
  fi
  sleep "$SLEEP"
done
SH
chmod +x {CLIENT_SCRIPT_NAME}
nohup {CLIENT_SCRIPT_NAME} > /tmp/{host}_client.log 2>&1 &
"""
    return mnexec_run(pid, script)

def start_ping_loop(pid, dest, interval, iterations, host):
    script = f"""cat > {PING_SCRIPT_NAME} <<'SH'
#!/bin/sh
DEST="{dest}"
INTERVAL="{interval}"
COUNT={int(iterations)}
i=0
while :
do
  i=$((i+1))
  echo "[ping_loop] iter $i -> $DEST" >> /tmp/{host}_generate.log 2>&1
  ping -c 1 "$DEST" >/dev/null 2>&1
  if [ "$COUNT" -ne 0 ] && [ "$i" -ge "$COUNT" ]; then
    break
  fi
  sleep "$INTERVAL"
done
SH
chmod +x {PING_SCRIPT_NAME}
nohup {PING_SCRIPT_NAME} > /tmp/{host}_ping.log 2>&1 &
"""
    return mnexec_run(pid, script)

# ------------------------------------------------------------------------------
# Stop / cleanup functions (pkill inside host namespaces)
# ------------------------------------------------------------------------------
def stop_clients(pid, host):
    # tries to pkill client script and client loggers
    return mnexec_run(pid, f"pkill -f {os.path.basename(CLIENT_SCRIPT_NAME)} || true; pkill -f wget || true; rm -f /tmp/{host}_client.log || true")

def stop_pings(pid, host):
    return mnexec_run(pid, f"pkill -f {os.path.basename(PING_SCRIPT_NAME)} || true; rm -f /tmp/{host}_ping.log || true")

def stop_servers(pid, host):
    # stop python http.server processes and remove logs optionally
    return mnexec_run(pid, f"pkill -f http.server || true; rm -f /tmp/{host}_http.log || true")

# ------------------------------------------------------------------------------
# Main flow
# ------------------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(description="Generate traffic inside existing Mininet topology")
    p.add_argument("--auto-stop", type=int, default=0, metavar="SECONDS",
                   help="Automatically stop all generated background jobs after SECONDS (0=never).")
    p.add_argument("--write-mininet-cmds", type=str, default="", metavar="FILE",
                   help="Write Mininet CLI commands to FILE so you can paste them into mininet> prompt.")
    p.add_argument("--no-start", action="store_true",
                   help="Do not start anything; only write mininet cmds (if --write-mininet-cmds provided).")
    return p.parse_args()

def main():
    args = parse_args()
    if os.geteuid() != 0:
        print("Please run as root (sudo).")
        sys.exit(1)

    all_hosts = set(list(SERVERS.keys()) + list(CLIENTS.keys()) + list(PINGS.keys()))

    # Optionally write mininet commands and exit (or continue)
    if args.write_mininet_cmds := args.write_mininet_cmds if hasattr(args, 'write_mininet_cmds') else args.write_mininet_cmds:
        if args.write_mininet_cmds:
            lines = build_mininet_commands()
            with open(args.write_mininet_cmds, "w") as f:
                f.write("\n".join(lines) + "\n")
            print(f"Wrote Mininet CLI commands to {args.write_mininet_cmds}.")
            print("You can paste the file contents into mininet> prompt or open the file for reference.")
            if args.no_start:
                return

    print("Locating Mininet host PIDs...")
    host_pids = {}
    for h in sorted(all_hosts):
        pid = find_host_pid(h)
        if not pid:
            print(f"Warning: host '{h}' pid not found (is topology running and host named '{h}' present?)")
        else:
            host_pids[h] = pid
            print(f"Found {h} -> pid {pid}")

    if args.no_start:
        print("No-start flag set; exiting after writing commands (if any).")
        return

    # Start servers
    for host, conf in SERVERS.items():
        pid = host_pids.get(host)
        if not pid:
            print(f"Skipping server {host}: pid not found.")
            continue
        print(f"Preparing server files on {host}...")
        ok = ensure_server_files(pid, conf, host)
        print("  files ok" if ok else "  files failed")
        print(f"Starting http server on {host}...")
        ok = start_server(pid, conf, host)
        print("  started" if ok else "  failed")

    time.sleep(1.2)  # give servers a moment

    # Start clients
    for host, (url, sleep_s, iters) in CLIENTS.items():
        pid = host_pids.get(host)
        if not pid:
            print(f"Skipping client {host}: pid not found.")
            continue
        print(f"Starting client loop on {host} -> {url} sleep={sleep_s}s iters={iters or 'inf'}")
        rc, out, err = start_client(pid, url, sleep_s, iters, host)
        if rc == 0:
            print("  client started")
        else:
            print("  client failed:", err.strip() or out.strip())

    # Start ping loops
    for host, (dest, interval, iters) in PINGS.items():
        pid = host_pids.get(host)
        if not pid:
            print(f"Skipping ping {host}: pid not found.")
            continue
        print(f"Starting ping loop on {host} -> {dest}")
        rc, out, err = start_ping_loop(pid, dest, interval, iters, host)
        if rc == 0:
            print("  ping started")
        else:
            print("  ping failed:", err.strip() or out.strip())

    # If auto-stop requested, wait then stop
    if args.auto_stop and args.auto_stop > 0:
        print(f"\nAuto-stop is active: the script will stop generated jobs after {args.auto_stop} seconds.")
        try:
            time.sleep(args.auto_stop)
            print("Auto-stop timeout reached — stopping clients/pings/servers...")
            # stop clients/pings/servers
            for host in sorted(all_hosts):
                pid = host_pids.get(host)
                if not pid:
                    continue
                print(f"Stopping clients on {host}...")
                stop_clients(pid, host)
                print(f"Stopping pings on {host}...")
                stop_pings(pid, host)
                if host in SERVERS:
                    print(f"Stopping server on {host}...")
                    stop_servers(pid, host)
            print("Auto-stop cleanup complete.")
        except KeyboardInterrupt:
            print("Auto-stop interrupted by user; leaving background jobs running.")

    else:
        print("\nTraffic generators started. (No auto-stop scheduled.)")

    print("\nPer-host logs inside Mininet hosts:")
    for host in sorted(all_hosts):
        print(f"  mininet> {host} tail -n 40 /tmp/{host}_generate.log  (or /tmp/{host}_client.log /tmp/{host}_ping.log)")

    print("\nTo stop manually (from host OS): use mnexec or from mininet> use pkill on each host, e.g.:")
    print("  mininet> h1 pkill -f send_http_client.sh")
    print("  mininet> h4 pkill -f http.server")
    print("  mininet> h3 pkill -f ping_loop.sh")

    # remain alive until user Ctrl-C (if desired)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting main script. Note: background jobs inside Mininet hosts may still run until killed.")
        sys.exit(0)

if __name__ == "__main__":
    main()
