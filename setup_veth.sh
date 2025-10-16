#!/bin/bash

echo "=== Veth Setup Script ==="

# Cleanup existing
echo "Cleaning up existing veth..."
sudo ip link delete veth-host 2>/dev/null
sudo ovs-vsctl del-port s2 veth-mininet 2>/dev/null

# Create veth pair
echo "Creating veth pair..."
sudo ip link add veth-host type veth peer name veth-mininet

# Configure interfaces
echo "Configuring interfaces..."
sudo ip link set veth-host up
sudo ip link set veth-mininet up
sudo ip link set veth-host promisc on
sudo ip link set veth-mininet promisc on

# Add to OVS
echo "Adding to Open vSwitch..."
sudo ovs-vsctl add-port s2 veth-mininet

# Setup mirror
echo "Setting up traffic mirror..."
sudo ovs-vsctl -- --id=@veth get Port veth-mininet \
  -- --id=@m create Mirror name=veth-mirror select-all=true output-port=@veth \
  -- set Bridge s2 mirrors=@m

# Verify
echo -e "\n=== Verification ==="
echo "Veth pair:"
ip link show | grep veth

echo -e "\nOVS configuration:"
sudo ovs-vsctl show | grep -A 2 veth

echo -e "\nMirror configuration:"
sudo ovs-vsctl list Mirror

echo -e "\n✓ Setup complete!"
echo "Test with: sudo tcpdump -i veth-host -c 10"
echo "Capture with: sudo python3 -m cicflowmeter.sniffer -i veth-host ./flow.csv"
