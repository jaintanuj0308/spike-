# test_live_api.py - Live network simulation showing actual JSON WebSocket payloads
import asyncio
import subprocess
import time
import sys
import urllib.request
import json
import os

CONFIG_PATH = "config.py"

# Original config backup container
original_config_content = ""

def backup_config():
    global original_config_content
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        original_config_content = f.read()

def restore_config():
    if original_config_content:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(original_config_content)
        print("[TEST SETUP] Original config.py restored.")

def write_test_config():
    test_config = """\"\"\"
Spike System Configuration - TEST OVERRIDE
\"\"\"
PLANT_TIME = 2
SPIKE_TIME = 5
DEFUSE_TIME = 2

GPIO_BUZZER = None
GPIO_LED_RED = None
GPIO_LED_GREEN = None
GPIO_7SEG_SEGMENTS = []
GPIO_7SEG_DIGITS = []

USB_DEVICE_MAP = {
    "ATTACKER_SERIAL_1": "A1",
    "DEFENDER_SERIAL_1": "D1",
}
ATTACKER_PREFIX = "A"
DEFENDER_PREFIX = "D"

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8001

ENABLE_GPIO = False
ENABLE_USB_MONITOR = False
"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(test_config)
    print("[TEST SETUP] Temporarily replaced config.py with short timers & hardware disabled.")


async def run_client_simulation():
    try:
        import websockets
    except ImportError:
        print("[ERROR] 'websockets' library is missing. Please run pip install websockets.")
        return

    uri = "ws://127.0.0.1:8001/ws"
    print(f"\n[CLIENT] Establishing WebSocket connection to {uri}...")
    
    async with websockets.connect(uri) as websocket:
        print("[CLIENT] Connection opened successfully!")
        
        # 1. Await initial state broadcast on connect
        msg = await websocket.recv()
        print(f"\n[WS PAYLOAD RECEIVED]\n{json.dumps(json.loads(msg), indent=2)}")
        
        # 2. Trigger planting start via REST request
        print("\n[CLIENT] Triggering HTTP POST /plant/A1 ...")
        await asyncio.to_thread(
            lambda: urllib.request.urlopen("http://127.0.0.1:8001/plant/A1", data=b"").read()
        )
        
        # 3. Read planting updates dynamically until we reach "planted"
        print("\n[CLIENT] Listening for planting events...")
        while True:
            msg = await websocket.recv()
            payload = json.loads(msg)
            print(f"[WS PAYLOAD RECEIVED]\n{json.dumps(payload, indent=2)}")
            if payload.get("state") == "planted":
                break
                
        # 4. Trigger defusal start via REST request
        print("\n[CLIENT] Triggering HTTP POST /defuse/D1 ...")
        await asyncio.to_thread(
            lambda: urllib.request.urlopen("http://127.0.0.1:8001/defuse/D1", data=b"").read()
        )
        
        # 5. Read defusing updates dynamically until we reach "defused"
        print("\n[CLIENT] Listening for defusal events...")
        while True:
            msg = await websocket.recv()
            payload = json.loads(msg)
            print(f"[WS PAYLOAD RECEIVED]\n{json.dumps(payload, indent=2)}")
            if payload.get("state") == "defused":
                break
            
        # 6. Reset round via REST request
        print("\n[CLIENT] Triggering HTTP POST /reset ...")
        await asyncio.to_thread(
            lambda: urllib.request.urlopen("http://127.0.0.1:8001/reset", data=b"").read()
        )
        
        # Receive final state after reset
        msg = await websocket.recv()
        print(f"[WS PAYLOAD RECEIVED]\n{json.dumps(json.loads(msg), indent=2)}")
        
    print("\n[CLIENT] Connection closed cleanly.")


def main():
    backup_config()
    
    server_process = None
    try:
        write_test_config()
        
        print("\n[TEST SETUP] Launching FastAPI App Server in background...")
        server_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8001"],
            cwd=os.getcwd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Give the server 2.5 seconds to spin up
        time.sleep(2.5)
        
        # Check if the process exited early
        exit_code = server_process.poll()
        if exit_code is not None:
            stdout, stderr = server_process.communicate()
            print(f"\n[ERROR] FastAPI App Server crashed on startup (Exit Code {exit_code})!")
            print(f"Stdout:\n{stdout}")
            print(f"Stderr:\n{stderr}")
            return
            
        # Start client simulator loop
        asyncio.run(run_client_simulation())
        
    except KeyboardInterrupt:
        print("\nSimulation aborted by user.")
    except Exception as e:
        print(f"\nSimulation failed: {e}")
    finally:
        if server_process:
            print("\n[TEST CLEANUP] Terminating background server...")
            server_process.terminate()
            try:
                stdout, stderr = server_process.communicate(timeout=2.0)
                if stdout:
                    print(f"Server Log Output:\n{stdout}")
                if stderr:
                    print(f"Server Error Output:\n{stderr}")
            except Exception:
                pass
            print("[TEST CLEANUP] Background server terminated.")
        restore_config()

if __name__ == "__main__":
    main()
