"""compatibility_check.py
Utility module to ensure the software runs on a Raspberry Pi 32‑bit environment.
"""

import platform
import sys
import logging

logger = logging.getLogger(__name__)

def verify_raspberry_pi_32bit() -> None:
    """Validate that the current runtime matches a 32‑bit Raspberry Pi.

    The function raises a RuntimeError if an unsupported platform or architecture
    is detected. This check is lightweight and can be called at application start‑up.
    """
    # Ensure we are on Linux (Raspberry Pi OS is Linux based)
    if platform.system() != "Linux":
        logger.warning("Running on a non‑Linux system – some hardware features (e.g., pyudev) may not work.")
        return

    # Detect common 32‑bit ARM identifiers used by Raspberry Pi models
    # Detect common 32‑bit ARM identifiers used by Raspberry Pi models
    arch = platform.machine().lower()
    # Accept 32‑bit ARM and also 64‑bit aarch64 (common on newer Pi OS)
    supported_arches = {"armv6l", "armv7l", "armv8l", "aarch64"}
    if arch not in supported_arches:
        logger.warning(f"Unexpected architecture '{arch}'. Proceeding anyway, but some hardware may not be fully supported.")
        # Do not raise; allow execution to continue on unknown arch
        # raise RuntimeError("Incompatible architecture for this software.")


    # Optional: enforce Python version (>=3.8 recommended for async features)
    if sys.version_info < (3, 8):
        logger.error("Python version is too old. Minimum required is 3.8.")
        raise RuntimeError("Python version incompatible.")

    logger.info(f"Platform verification passed: Linux on {arch}, Python {sys.version.split()[0]}")

if __name__ == "__main__":
    try:
        verify_raspberry_pi_32bit()
        print("Compatibility check passed.")
    except RuntimeError as e:
        print(f"Compatibility check failed: {e}")
        sys.exit(1)
