#!/bin/bash

# Step 1: Buat Dockerfile dengan nginx, iperf3, sysctl tweak
cat <<EOF > Dockerfile
FROM ubuntu:22.04

# Instal tools penting
RUN apt update && \
    apt install -y iproute2 iputils-ping nginx htop curl iperf3 net-tools tcpdump && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# Tambahkan file dummy
RUN mkdir -p /var/www/html/static && \
    mkdir -p /var/www/html/api

RUN dd if=/dev/zero of=/var/www/html/bigfile.bin bs=1M count=100 && \
    dd if=/dev/zero of=/var/www/html/mediumfile.bin bs=1M count=10 && \
    dd if=/dev/urandom of=/var/www/html/smallfile.bin bs=1M count=1

RUN echo "<!DOCTYPE html><html><body><h1>Welcome to Nginx!</h1></body></html>" > /var/www/html/index.html && \
    echo "body { background-color: #f0f0f0; }" > /var/www/html/static/style.css && \
    echo "console.log('Hello from JS');" > /var/www/html/static/script.js && \
    echo '{"data": {"id": 1, "name": "test"}}' > /var/www/html/api/data.json && \
    echo "<!DOCTYPE html><html><body><form action='/login' method='post'>...</form></body></html>" > /var/www/html/login.html && \
    echo "<!DOCTYPE html><html><body><h1>404 Not Found</h1></body></html>" > /var/www/html/404.html

# Konfigurasi nginx: ubah root dan matikan token
RUN echo "server { \
    listen 80; \
    server_name localhost; \
    root /var/www/html; \
    index index.html; \
    location / { try_files \$uri \$uri/ =404; } \
}" > /etc/nginx/conf.d/default.conf && \
    echo "client_max_body_size 100M;" > /etc/nginx/conf.d/client_max_body_size.conf && \
    echo "server_tokens off;" >> /etc/nginx/conf.d/security.conf

# Tweak sysctl
RUN echo 'net.ipv4.tcp_syncookies = 0' >> /etc/sysctl.conf && \
    echo 'net.ipv4.tcp_max_syn_backlog = 64' >> /etc/sysctl.conf && \
    echo 'net.ipv4.tcp_abort_on_overflow = 1' >> /etc/sysctl.conf

# Jalankan nginx + apply sysctl
CMD ["bash", "-c", "sysctl -p && nginx -g 'daemon off;'"]
EOF

# Step 2: Build Image
echo "[•] Membuild image Docker nginx dengan tweak sysctl dan file dummy..."
docker build -t nginx-full .

# Step 3: Bersihkan container lama
echo "[•] Menghapus container lama jika ada..."
docker rm -f web-nginx 2>/dev/null

# Step 4: Jalankan container dengan batas resource + mode manual networking
echo "[•] Menjalankan container..."
docker run -dit \
  --name web-nginx \
  --cpus="0.2" \
  --memory="128m" \
  --memory-swap="128m" \
  --privileged \
  --cap-add=NET_ADMIN \
  --network=none \
  --sysctl net.ipv4.conf.all.rp_filter=0 \
  --sysctl net.ipv4.conf.default.rp_filter=0 \
  -p 8080:80 \
  nginx-full

# Step 5: Setup Jaringan (menghindari konflik eth0 → pakai eth1)
echo "[•] Menyiapkan veth pair dan sambungkan ke s1..."
ip link add veth-host type veth peer name veth-docker
PID=$(docker inspect -f '{{.State.Pid}}' web-nginx)
ip link set veth-docker netns $PID
docker exec web-nginx ip link set veth-docker name eth1
docker exec web-nginx ip addr add 10.0.0.2/24 dev eth1
docker exec web-nginx ip link set eth1 up
ip link set veth-host up
ovs-vsctl add-port s1 veth-host

# Step 6: Selesai
echo "[✓] Server Nginx siap dan terhubung ke s1:"
echo "---------------------------------------------"
echo "1. bigfile.bin      (100MB)  -> http://10.0.0.2/bigfile.bin"
echo "2. mediumfile.bin   (10MB)   -> http://10.0.0.2/mediumfile.bin"
echo "3. smallfile.bin    (1MB)    -> http://10.0.0.2/smallfile.bin"
echo "4. index.html       (HTML)   -> http://10.0.0.2/"
echo "5. static/style.css (CSS)    -> http://10.0.0.2/static/style.css"
echo "6. static/script.js (JS)     -> http://10.0.0.2/static/script.js"
echo "7. api/data.json    (JSON)   -> http://10.0.0.2/api/data.json"
echo "8. login.html       (Form)   -> http://10.0.0.2/login.html"
echo "9. 404.html         (Error)  -> http://10.0.0.2/nonexistent"
echo "---------------------------------------------"
echo "Gunakan 'docker exec -it web-nginx htop' untuk monitoring."
echo "Gunakan 'docker exec -it web-nginx netstat -ant' untuk melihat koneksi TCP."
