#!/usr/bin/env bash
# install.sh - Installs dependencies and optionally sets up systemd service for Spike RPi

set -e

echo "===================================================="
echo "Installing dependencies for Raspberry Pi Spike System"
echo "===================================================="

# 1. Install system dependencies
echo "Updating apt repositories and installing python3-pip, python3-venv..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv python3-dev build-essential udev

# 2. Create virtual environment
echo "Creating virtual environment in 'venv'..."
python3 -m venv venv

# 3. Activate venv and install python requirements
echo "Installing pip requirements..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Prompt for systemd service setup
echo "===================================================="
read -p "Do you want to install the Spike systemd service? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    SCRIPT_PATH=$(realpath main.py)
    DIR_PATH=$(dirname "$SCRIPT_PATH")
    VENV_PYTHON="$DIR_PATH/venv/bin/python"

    echo "Creating systemd service configuration..."
    
    SERVICE_FILE="/etc/systemd/system/spike.service"
    sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=Spike Tactical Game Backend Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$DIR_PATH
ExecStart=$VENV_PYTHON -m uvicorn main:app --host 0.0.0.0 --port 8001
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    echo "Reloading systemd, enabling and starting spike service..."
    sudo systemctl daemon-reload
    sudo systemctl enable spike.service
    sudo systemctl start spike.service
    
    echo "Systemd service successfully set up and started!"
    echo "You can check status with: sudo systemctl status spike.service"
    echo "You can view logs with: journalctl -u spike.service -f"
fi

echo "===================================================="
echo "Installation complete!"
echo "To run manually: ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8001"
echo "===================================================="
