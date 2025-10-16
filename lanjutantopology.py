def setupMirrorPorts():
    """Setup mirror ports untuk capture traffic"""
    print("Setting up mirror ports for traffic monitoring...")
    
    # Buat virtual interface untuk monitoring
    os.system('sudo ip link add mon0 type dummy')
    os.system('sudo ip link set mon0 up')
    
    # Attach ke switch s2 (yang paling banyak traffic)
    os.system('sudo ovs-vsctl add-port s2 mon0')
    
    # Setup mirroring - mirror semua traffic di s2 ke mon0
    mirror_cmd = '''sudo ovs-vsctl -- --id=@mon0 get Port mon0 \
                    -- --id=@m create Mirror name=mymirror select-all=true output-port=@mon0 \
                    -- set Bridge s2 mirrors=@m'''
    os.system(mirror_cmd)
    
    print("Mirror port 'mon0' created successfully!")
    print("Use 'mon0' interface for CICFlowMeter capture")

setupMirrorPorts()

    print("\n=== Network Ready ===")
    print("Available interfaces for capture:")
    os.system('ip link show | grep -E "s[0-9]-eth|mon0"')
    print("\nRecommended: Use 'mon0' interface for CICFlowMeter")
    print("Example: sudo python3 -m cicflowmeter.sniffer -i mon0 -o /path/to/output\n")
    
    print("Jalankan CLI Mininet. Coba periksa ping antar host dan topologi di ONOS.")
    CLI(net)

    # Cleanup
    print("Cleaning up mirror ports...")
    os.system('sudo ovs-vsctl clear Bridge s2 mirrors')
    os.system('sudo ovs-vsctl del-port s2 mon0')
    os.system('sudo ip link delete mon0')

