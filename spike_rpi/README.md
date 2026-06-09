# Raspberry Pi Spike Software System

Production-ready, event-driven game state manager for a real Raspberry Pi 4-based spike (tactical field bomb device). Powered by FastAPI, WebSockets, `pyudev` for automated pendrive insertion and removal detection, and `RPi.GPIO` for hardware peripherals control.

This system is configured to match the assignments in [config.py](file:///c:/Users/Admin/Desktop/spike/spike_rpi/config.py).

---

## Hardware Wiring Guide

Connect your physical peripherals to the Raspberry Pi 4 GPIO pins mapped below:

```
                  +-----------------------------------------+
                  |         Raspberry Pi 4 Header           |
                  |                                         |
                  |  GPIO 18 (Pin 12) ---------> Buzzer (+) |
                  |  GPIO 23 (Pin 16) ---------> Red LED (+)|
                  |  GPIO 24 (Pin 18) ---------> Green LED(+)|
                  |                                         |
                  |  Direct 7-Segment Multiplexed Display   |
                  |  Digit 1 (Tens):   GPIO 12 (Pin 32)     |
                  |  Digit 2 (Ones):   GPIO 25 (Pin 22)     |
                  |  Segment A to DP:  GPIO 5, 6, 13, 19,   |
                  |                    26, 16, 20, 21       |
                  |                                         |
                  |  GND     (Pin 39) ---------> Ground (-) |
                  +-----------------------------------------+
```

---

## Installation & Startup

### Automated Installer (Debian/Raspberry Pi OS)
Execute the helper script to install dependencies, configure a python virtual environment, and optionally set up a systemd boot service:
```bash
chmod +x install.sh
./install.sh
```

### Manual Installation
1. Install system utilities:
   ```bash
   sudo apt-get update
   sudo apt-get install python3-pip python3-venv python3-dev build-essential udev -y
   ```
2. Set up virtual environment and install packages:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Run the uvicorn API & WebSocket server:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8001 --reload
   ```

---

## USB Key Integration Configuration

To calibrate physical USB keys for the game, run the server and plug in your drives. If they are not mapped, the application will dump their hardware fingerprints to stdout:

```
==============================================
      UNRECOGNIZED USB DEVICE DETECTED        
==============================================
  Device Path : /dev/sdX
  Short Serial: 001A9C             <--- Use this ID
  Vendor ID   : 0781
  Model ID    : 5571               <--- Or combination: "0781:5571"
==============================================
```

Copy either identifier into [config.py](file:///c:/Users/Admin/Desktop/spike/spike_rpi/config.py):
```python
USB_DEVICE_MAP = {
    "001A9C": "A1",      # Attacker Key
    "0951:1666": "D1",   # Defender Key
}
```

---

## API & Communication Specifications

### WebSockets Integration
Connect dashboard monitors or field panels using: `ws://[pi-ip]:8001/ws`

*   **State Updates Broadcasts (Server -> Clients):**
    ```json
    {
      "event": "state_update",
      "state": "planted",
      "plant_remaining": 0,
      "spike_remaining": 34,
      "defuse_remaining": 60,
      "planter_id": "A1",
      "defuser_id": null
    }
    ```
*   ** referee overrides control commands (Client -> Server):**
    *   Trigger Player Death: `{"event": "player_killed", "player_id": "A1"}`
    *   Reset Spike Round: `{"event": "reset_round"}`
    *   Force Detonation: `{"event": "force_explode"}`

### HTTP Rest Interface
*   `GET /status`: Retrieves current JSON state snapshot.
*   `POST /reset`: Resets state parameters to `idle`.
*   `POST /kill/{player_id}`: Triggers player death logic (e.g. key pull override).
*   `POST /plant/{player_id}`: Manually starts planting (diagnostic tool).
*   `POST /defuse/{player_id}`: Manually starts defusing (diagnostic tool).

---

## Validation & Testing Tools

We provide tools that work out of the box on Windows/macOS/Linux without any GPIO dependencies:

1.  **Automated State Verification Pipeline:**
    Runs comprehensive state transition assertions:
    ```bash
    python test_scenario.py
    ```
2.  **Interactive Terminal Console Simulator:**
    Allows manual triggering of USB keys inserts/ejects using keypress hooks:
    ```bash
    python test_spike.py
    ```
