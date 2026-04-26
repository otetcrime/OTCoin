#!/bin/bash
# OTCoin Node Setup Script v1.0
# One Transaction. All Chains.

echo "=================================================="
echo "  🪙 OTCoin Node Setup"
echo "  One Transaction. All Chains."
echo "=================================================="

# Cek OS
if [ -f /etc/debian_version ]; then
    echo "✅ Detected: Debian/Ubuntu"
else
    echo "⚠️  Recommended: Ubuntu 20.04/22.04"
fi

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
apt update -q && apt install -y python3 python3-pip git

# Install Python packages
echo ""
echo "📦 Installing Python packages..."
pip3 install websockets ecdsa flask flask-cors --break-system-packages 2>/dev/null || pip3 install websockets ecdsa flask flask-cors

# Clone repo
echo ""
echo "📥 Downloading OTCoin..."
if [ -d "OTCoin" ]; then
    cd OTCoin && git pull
else
    git clone https://github.com/OTCoinFoundation/OTCoin.git
    cd OTCoin
fi

# Buat systemd service
echo ""
echo "⚙️  Setting up auto-start..."
cat > /etc/systemd/system/otcoin-node.service << 'SERVICE'
[Unit]
Description=OTCoin Node
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/OTCoin
ExecStart=/usr/bin/python3 /root/OTCoin/node.py --port 6001 --peers ws://76.13.192.203:6001
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE

systemctl enable otcoin-node
systemctl start otcoin-node

echo ""
echo "=================================================="
echo "✅ OTCoin Node berhasil diinstall!"
echo ""
echo "📡 Node kamu terhubung ke: ws://76.13.192.203:6001"
echo "🌐 Network: OTCoin Mainnet v2"
echo ""
echo "Perintah berguna:"
echo "  systemctl status otcoin-node  # Cek status"
echo "  systemctl restart otcoin-node # Restart node"
echo "  journalctl -u otcoin-node -f  # Lihat log"
echo "=================================================="
