# main.py - Application entry point, asyncio startup/shutdown tasks, and websocket routes
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import config
from spike_state import SpikeState
from usb_monitor import USBMonitor
from gpio_output import gpio_handler
from tick import tick_loop

from websocket_manager import ws_manager
from backend_client import init_backend_client
import spike_logic
from compatibility_check import verify_raspberry_pi_32bit


# Configure logs format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("spike_main")

# State and tasks lifecycle containers
state_instance = SpikeState()
backend_client = init_backend_client(state_instance)
background_tasks = set()
usb_monitor_instance = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles async background loops and peripheral monitors startup & shutdown."""

    try:
        verify_raspberry_pi_32bit()
    except RuntimeError as e:
        logger.warning(f"Compatibility check failed but continuing: {e}")
    
    # 1. Start the async 1-second countdown tick loop and backend client
    backend_task = asyncio.create_task(backend_client.run())
    background_tasks.add(backend_task)
    backend_task.add_done_callback(background_tasks.discard)
    tick_task = asyncio.create_task(tick_loop(state_instance))
    background_tasks.add(tick_task)
    tick_task.add_done_callback(background_tasks.discard)
    
    # 2. Setup and register physical/mock USB detection monitor
    global usb_monitor_instance
    usb_monitor_instance = USBMonitor(state_instance)
    usb_monitor_instance.start()
    
    logger.info("Spike system initialized and fully operational.")
    
    yield
    
    # Clean up operations on shutdown
    logger.info("Stopping Spike System and releasing hardware peripherals...")
    
    # Cancel all background tasks
    for task in list(background_tasks):
        task.cancel()
        
    # Wait for tasks completion
    if background_tasks:
        await asyncio.gather(*background_tasks, return_exceptions=True)
        
    # Clean up GPIO pins
    gpio_handler.cleanup()
    logger.info("Shutdown completed.")

# Instantiate FastAPI with lifespan hooks
app = FastAPI(
    title="Raspberry Pi Spike Tactical Game System",
    lifespan=lifespan
)

# Enable CORS for dashboards, umpiring apps, and diagnostics
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register SPIKE State dependency injection override


# Mount REST endpoints



@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket channel for dashboard client status monitors and referee controls.
    Maintains heartbeat updates, sends initial state, and accepts game commands.
    """
    initial_dict = await state_instance.to_dict()
    # Accept client and dispatch initial state
    await ws_manager.connect(websocket, initial_dict)
    
    try:
        while True:
            # Await client command messages
            data = await websocket.receive_json()
            
            event = data.get("event")
            if not event:
                logger.warning(f"Received JSON with missing event identifier: {data}")
                continue
                
            logger.info(f"Received WS control event: {event}")
            
            if event == "player_killed":
                player_id = data.get("player_id")
                if player_id:
                    await spike_logic.on_player_killed(state_instance, player_id)
                else:
                    logger.warning("player_killed event missing player_id")
                    
            elif event == "reset_round":
                await spike_logic.reset_round(state_instance)
                
            elif event == "plant":
                player_id = data.get("player_id")
                if player_id:
                    await spike_logic.start_plant(state_instance, player_id)
                else:
                    logger.warning("plant event missing player_id")
            elif event == "defuse":
                player_id = data.get("player_id")
                if player_id:
                    skip_role_check = data.get("skip_role_check", False)
                    await spike_logic.start_defuse(state_instance, player_id, skip_role_check=skip_role_check)
                else:
                    logger.warning("defuse event missing player_id")
                
            else:
                logger.warning(f"Unknown control command event: {event}")
                
    except WebSocketDisconnect:
        logger.info("WebSocket connection dropped by client.")
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket execution error: {e}", exc_info=True)
        ws_manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    # Start ASGI runner manually using configurations from config.py
    uvicorn.run(
        "main:app",
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        log_level="info"
    )
