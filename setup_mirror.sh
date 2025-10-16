#!/bin/bash

# Setup mirror port untuk monitoring semua traffic di switch s1, s2, dan s3
echo "Setting up mirror ports..."

# Mirror untuk s1
sudo ovs-vsctl -- --id=@m get port s1 \
  -- --id=@s1-eth1 get port s1-eth1 \
  -- create mirror name=mirror-s1 select-all=true output-port=@m

# Mirror untuk s2
sudo ovs-vsctl -- --id=@m get port s2 \
  -- --id=@s2-eth1 get port s2-eth1 \
  -- --id=@s2-eth2 get port s2-eth2 \
  -- --id=@s2-eth3 get port s2-eth3 \
  -- --id=@s2-eth4 get port s2-eth4 \
  -- create mirror name=mirror-s2 select-all=true output-port=@m

# Mirror untuk s3
sudo ovs-vsctl -- --id=@m get port s3 \
  -- --id=@s3-eth1 get port s3-eth1 \
  -- --id=@s3-eth2 get port s3-eth2 \
  -- --id=@s3-eth3 get port s3-eth3 \
  -- create mirror name=mirror-s3 select-all=true output-port=@m

echo "Mirror ports setup complete!"
