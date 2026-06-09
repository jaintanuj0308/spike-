"""
Spike System Configuration
──────────────────────────
All hardware pin assignments and game timer durations.
Edit ONLY this file to adjust game parameters or wiring.
"""

# ──────────────────────────────────────
# TIMER DURATIONS (seconds)
# ──────────────────────────────────────
PLANT_TIME: int = 60        # Seconds to complete planting
SPIKE_TIME: int = 180        # Seconds before spike explodes after planted
DEFUSE_TIME: int = 60       # Seconds to complete defusing
ROUND_TIME: int = 600       # Seconds for a full game round

# ──────────────────────────────────────
# GPIO PIN ASSIGNMENTS (BCM numbering)
# ──────────────────────────────────────
GPIO_BUZZER: int = 18       # PWM-capable pin for buzzer
GPIO_LED_RED: int = 23      # Red LED — PLANTED / DEFUSING indicator
GPIO_LED_GREEN: int = 24    # Green LED — DEFUSED indicator

# 7-segment display pins (active-low common-cathode assumed)
# Segments: A, B, C, D, E, F, G, DP
GPIO_7SEG_SEGMENTS: list[int] = [5, 6, 13, 19, 26, 16, 20, 21]
# Digit select pins (left-to-right)
GPIO_7SEG_DIGITS: list[int] = [12, 25]  # 2-digit display

# ──────────────────────────────────────
# USB PENDRIVE IDENTIFICATION
# ──────────────────────────────────────
# Map USB serial numbers to player roles.
# Run `udevadm info --query=all --name=/dev/sdX` to find your pendrive's serial.
# Format: { "serial_number": "player_id" }
USB_DEVICE_MAP: dict[str, str] = {
    "ATTACKER_SERIAL_1": "A1",
    "DEFENDER_SERIAL_1": "D1",
    # Add more pendrives as needed:
    # "ANOTHER_SERIAL": "A2",
}

# Prefixes that identify attackers vs defenders
ATTACKER_PREFIX: str = "A"
DEFENDER_PREFIX: str = "D"

# ──────────────────────────────────────
# NETWORK
# ──────────────────────────────────────
SERVER_HOST: str = "0.0.0.0"
SERVER_PORT: int = 8001
BACKEND_WS_URL: str = "ws://localhost:8000/ws/spike"  # Backend server WS endpoint

# ──────────────────────────────────────
# HARDWARE FEATURE FLAGS
# ──────────────────────────────────────
# Set to False to disable hardware modules when running off-Pi (development)
ENABLE_GPIO: bool = True
ENABLE_USB_MONITOR: bool = True
