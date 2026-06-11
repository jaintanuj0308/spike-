# spike_logic.py - Core game event handlers and state transitions
import sys
import os
import asyncio
import logging
from spike_state import SpikeState, StateData
import config
from websocket_manager import ws_manager
from gpio_output import gpio_handler
import backend_client

logger = logging.getLogger("spike_logic")

def print_spike_state(data: StateData):
    """Prints the complete state of the spike in a formatted block."""
    print("========================")
    print("       SPIKE STATE      ")
    print("========================")
    print(f"  State            : {data.state.upper()}")
    print(f"  Plant Remaining  : {data.plant_remaining}s")
    spike_line = f"  Spike Remaining  : {data.spike_remaining}s"
    if getattr(data, 'spike_paused', False):
        spike_line += " (paused)"
    print(spike_line)
    print(f"  Defuse Remaining : {data.defuse_remaining}s")
    print(f"  Planter          : {data.planter_id or 'None'}")
    print(f"  Defuser          : {data.defuser_id or 'None'}")
    print("========================")
    sys.stdout.flush()

async def broadcast_state(spike_state: SpikeState):
    """Broadcasts the current state to all connected WebSocket clients."""
    state_dict = await spike_state.to_dict()
    payload = {
        "event": "state_update",
        **state_dict
    }
    await ws_manager.broadcast(payload)

async def start_plant(spike_state: SpikeState, player_id: str) -> bool:
    """Transitions state from IDLE to PLANTING."""
    # State verification
    data = await spike_state.get_state()
    if data.state != "idle":
        logger.warning(f"Cannot start planting from state: {data.state}")
        return False

    # Attacker role validation
    if not player_id.startswith(config.ATTACKER_PREFIX):
        logger.warning(f"Role mismatch: Non-attacker '{player_id}' tried to plant.")
        return False
    
    await spike_state.update(
        state="planting",
        plant_remaining=config.PLANT_TIME,
        planter_id=player_id,
        round_paused=True
    )
    new_data = await spike_state.get_state()
    print_spike_state(new_data)
    await broadcast_state(spike_state)
    await notify_backend({"event": "spike_planting", "player_id": player_id})
    gpio_handler.on_state_change(new_data.state)
    return True

async def spike_planted(spike_state: SpikeState) -> bool:
    """Transitions state from PLANTING to PLANTED."""
    data = await spike_state.get_state()
    if data.state != "planting":
        logger.warning(f"Cannot plant spike from state: {data.state}")
        return False
    
    await spike_state.update(
        state="planted",
        plant_remaining=0,
        spike_remaining=config.SPIKE_TIME,
        defuse_remaining=config.DEFUSE_TIME
    )
    new_data = await spike_state.get_state()
    print_spike_state(new_data)
    await broadcast_state(spike_state)
    await notify_backend({"event": "spike_planted"})
    gpio_handler.on_state_change(new_data.state)
    return True

async def start_defuse(spike_state: SpikeState, player_id: str, skip_role_check: bool = False) -> bool:
    """Transitions state from PLANTED to DEFUSING.
    
    Args:
        spike_state: The current spike state.
        player_id: The player attempting to defuse.
        skip_role_check: If True, bypass defender role validation.
            Used when defuse is triggered by USB removal (hardware event)
            rather than by USB insertion (player identification).
    """
    # State verification
    data = await spike_state.get_state()
    if data.state != "planted":
        logger.warning(f"Cannot start defusal from state: {data.state}")
        return False

    # Defender role validation (skipped for hardware-triggered defuse)
    if not skip_role_check and not player_id.startswith(config.DEFENDER_PREFIX):
        logger.warning(f"Role mismatch: Non-defender '{player_id}' tried to defuse.")
        return False
    
    await spike_state.update(
        state="defusing",
        defuser_id=player_id,
        spike_paused=True
    )
    new_data = await spike_state.get_state()
    print_spike_state(new_data)
    await broadcast_state(spike_state)
    await notify_backend({"event": "defuse_started", "player_id": player_id})
    gpio_handler.on_state_change(new_data.state)
    return True

async def cancel_defuse(spike_state: SpikeState) -> bool:
    """Cancels an in-progress defuse: returns to PLANTED, resets defuse timer,
    and resumes the spike countdown."""
    data = await spike_state.get_state()
    if data.state != "defusing":
        logger.warning(f"Cannot cancel defuse from state: {data.state}")
        return False

    logger.info(f"Defuse cancelled. Returning to PLANTED, resetting defuse timer to {config.DEFUSE_TIME}s.")
    await spike_state.update(
        state="planted",
        defuser_id=None,
        defuse_remaining=config.DEFUSE_TIME,  # Reset to full 60s
        spike_paused=False  # Resume spike countdown
    )
    new_data = await spike_state.get_state()
    print_spike_state(new_data)
    await broadcast_state(spike_state)
    # Notify backend so it resumes the spike countdown timer
    await notify_backend({"event": "cancel_defuse"})
    gpio_handler.on_state_change(new_data.state)
    return True

async def on_player_killed(spike_state: SpikeState, player_id: str) -> bool:
    """Handles a player being killed (removing their USB key)."""
    data = await spike_state.get_state()
    
    if data.state == "planting" and data.planter_id == player_id:
        # Attacker planter killed: return to IDLE, reset planting timer, clear planter_id
        await spike_state.update(
            state="idle",
            plant_remaining=config.PLANT_TIME,
            planter_id=None,
            round_paused=False
        )
        new_data = await spike_state.get_state()
        print_spike_state(new_data)
        await broadcast_state(spike_state)
        # Notify backend so it cancels its plant tick loop and resumes the round timer
        await notify_backend({"event": "cancel_plant", "player_id": player_id})
        gpio_handler.on_state_change(new_data.state)
        return True
        
    elif data.state == "defusing" and data.defuser_id == player_id:
        # Defender defuser killed: pause defusing, return to PLANTED, resume spike timer
        await spike_state.update(
            state="planted",
            defuser_id=None,
            spike_paused=False
        )
        new_data = await spike_state.get_state()
        print_spike_state(new_data)
        await broadcast_state(spike_state)
        # Notify backend so it cancels its defuse tick loop and resumes the spike countdown
        await notify_backend({"event": "cancel_defuse"})
        gpio_handler.on_state_change(new_data.state)
        return True
        
    logger.debug(f"Player killed event for '{player_id}' ignored. Current state: {data.state}")
    return False

async def explode(spike_state: SpikeState):
    """Spike exploded — ATTACKERS WIN. Announce result."""
    await spike_state.update(
        state="exploded",
        spike_remaining=0
    )
    new_data = await spike_state.get_state()
    print_spike_state(new_data)
    await broadcast_state(spike_state)
    await notify_backend({"event": "attackers_win"})
    gpio_handler.trigger_explosion()

    print("\n" + "=" * 40)
    print("   💥  ATTACKERS WON — SPIKE EXPLODED!  💥")
    print("=" * 40 + "\n")
    sys.stdout.flush()

async def defuse_success(spike_state: SpikeState):
    """Spike defused — DEFENDERS WIN. Announce result."""
    await spike_state.update(
        state="defused",
        defuse_remaining=0
    )
    new_data = await spike_state.get_state()
    print_spike_state(new_data)
    await broadcast_state(spike_state)
    await notify_backend({"event": "defuse_success"})
    gpio_handler.trigger_defused()

    print("\n" + "=" * 40)
    print("   🛡️  DEFENDERS WON — SPIKE DEFUSED!  🛡️")
    print("=" * 40 + "\n")
    sys.stdout.flush()

async def reset_round(spike_state: SpikeState):
    """Resets the entire game round back to IDLE."""
    await spike_state.reset()
    new_data = await spike_state.get_state()
    print_spike_state(new_data)
    await broadcast_state(spike_state)
    gpio_handler.on_state_change(new_data.state)

async def notify_backend(event: dict):
    """Broadcasts an outbound event dict to all WS clients and the backend."""
    await ws_manager.broadcast(event)
    if backend_client.backend_client is not None:
        await backend_client.backend_client.send_event(event)

async def start_round(spike_state: SpikeState):
    """Marks the round as active and unpaused."""
    await spike_state.update(round_active=True, round_paused=False)
    new_data = await spike_state.get_state()
    print_spike_state(new_data)
    await broadcast_state(spike_state)
