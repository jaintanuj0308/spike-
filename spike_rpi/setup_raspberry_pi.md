# Raspberry Pi Physical Hardware Setup Guide

This guide details the physical hardware wiring, system configuration, and deployment procedures to run the Spike Tactical Game System on a Raspberry Pi 4.

---

## 1. Physical Hardware Wiring

We use **Broadcom (BCM)** pin numbers in the configuration file. Below is the mapping from the BCM pin to the physical header pins of the Raspberry Pi 4.

### Wiring Reference Table

| Component | BCM Pin | Physical Pin | Connection Details |
| :--- | :--- | :--- | :--- |
| **Buzzer (+)** | GPIO 18 | Pin 12 | Positive anode. Connected to GND on Pin 14. |
| **Red LED (+)** | GPIO 23 | Pin 16 | Connect in series with a **220Ω - 330Ω resistor** to prevent damage. |
| **Green LED (+)** | GPIO 24 | Pin 18 | Connect in series with a **220Ω - 330Ω resistor** to prevent damage. |
| **Digit 1 select (Tens)**| GPIO 12 | Pin 32 | Cathode pin for Left digit. |
| **Digit 2 select (Ones)**| GPIO 25 | Pin 22 | Cathode pin for Right digit. |
| **Segment A** | GPIO 5 | Pin 29 | Segment A anode. |
| **Segment B** | GPIO 6 | Pin 31 | Segment B anode. |
| **Segment C** | GPIO 13 | Pin 33 | Segment C anode. |
| **Segment D** | GPIO 19 | Pin 35 | Segment D anode. |
| **Segment E** | GPIO 26 | Pin 37 | Segment E anode. |
| **Segment F** | GPIO 16 | Pin 36 | Segment F anode. |
| **Segment G** | GPIO 20 | Pin 38 | Segment G anode. |
| **Segment DP** | GPIO 21 | Pin 40 | Segment DP (decimal point) anode. |
| **Ground (GND)** | GND | Pin 39 (or 14) | Common negative ground rail for all components. |

---

## 2. Operating System & System Setup

We recommend using **Raspberry Pi OS (64-bit Lite)** to keep the system fast and headless.

### Step 1: Clone/Copy the Code
Log in to your Raspberry Pi terminal and copy this project folder `spike_rpi` under `/home/pi/spike_rpi`.

### Step 2: Establish Permissions for USB Monitoring
`pyudev` reads Netlink kernel event sockets. To listen to USB insertions/ejections without requiring root/sudo privileges:
1. Add your standard system user (e.g. `pi`) to the `plugdev` group:
   ```bash
   sudo usermod -aG plugdev $USER
   ```
2. Apply changes by logging out and logging back in, or run:
   ```bash
   newgrp plugdev
   ```

### Step 3: Run the Automated Installer
Configure the Python environment and system dependencies:
```bash
cd /home/pi/spike_rpi
chmod +x install.sh
./install.sh
```
When prompted: `Do you want to install the Spike systemd service? (y/N)`, answer **`y`**. This registers the script to run automatically in the background on boot.

---

## 3. Calibrating Attacker & Defender USB Devices

Every USB flash drive contains a unique serial number or vendor/model identifier. To map them:

1. Stop the background systemd service if running:
   ```bash
   sudo systemctl stop spike.service
   ```
2. Launch the application manually so you can monitor console logs:
   ```bash
   ./venv/bin/python main.py
   ```
3. Plug in your physical **Attacker** USB drive. The terminal will print:
   ```
   ==============================================
         UNRECOGNIZED USB DEVICE DETECTED        
   ==============================================
     Device Path : /dev/sdb1
     Short Serial: 07085521C534F181
     Vendor ID   : 0781
     Model ID    : 5571
     Config Key  : 0781:5571
   ==============================================
   ```
4. Copy either the `Short Serial` or the `Config Key`. Open `config.py` and register it:
   ```python
   USB_DEVICE_MAP = {
       "07085521C534F181": "A1",  # Attacker Key
   }
   ```
5. Repeat the process for the **Defender** USB drive (e.g., mapping to `"D1"`).
6. Press `Ctrl+C` to close the manual server, and restart the background system service:
   ```bash
   sudo systemctl start spike.service
   ```

---

## 4. Troubleshooting & Logging

If the system doesn't behave as expected, check the live logs using systemd:

*   **View Real-Time Logs:**
    ```bash
    journalctl -u spike.service -f
    ```
*   **Check Service Status:**
    ```bash
    sudo systemctl status spike.service
    ```
*   **Restart the Application:**
    ```bash
    sudo systemctl restart spike.service
    ```
