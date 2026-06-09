# tick.py - Periodic 1-second system tick loop
import asyncio
import logging
from spike_state import SpikeState, StateData
import spike_logic
from gpio_output import gpio_handler

logger = logging.getLogger("spike_tick")

def print_live_line(data: StateData):
    """Prints the live status line to stdout."""
    state_str = f"{data.state.upper():<10}"
    spike_part = f"Spike={data.spike_remaining:3d}s"
    if getattr(data, 'spike_paused', False):
        spike_part += " (paused)"
    print(
        f"[LIVE] State={state_str} | "
        f"Plant={data.plant_remaining:3d}s | "
        f"{spike_part} | "
        f"Defuse={data.defuse_remaining:3d}s",
        flush=True
    )

async def tick_loop(spike_state: SpikeState):
    """
    Periodic task running every 1 second to update spike countdowns,
    trigger state transitions, broadcast updates, and drive GPIO pulses.
    """
    logger.info("Spike tick loop started.")
    try:
        while True:
            # Run exactly once per second
            await asyncio.sleep(1)
            
            data = await spike_state.get_state()
            
            if data.state == "planting":
                new_plant = data.plant_remaining - 1
                if new_plant <= 0:
                    await spike_logic.spike_planted(spike_state)
                else:
                    await spike_state.update(plant_remaining=new_plant)
                    await spike_logic.broadcast_state(spike_state)
                    
            elif data.state == "planted":
                new_spike = data.spike_remaining - 1
                if new_spike <= 0:
                    await spike_logic.explode(spike_state)
                else:
                    await spike_state.update(spike_remaining=new_spike)
                    await spike_logic.broadcast_state(spike_state)
                    
            elif data.state == "defusing":
                new_defuse = data.defuse_remaining - 1

                # Check explosion condition first (spike timer is paused)
                if data.spike_remaining <= 0:
                    await spike_logic.explode(spike_state)
                elif new_defuse <= 0:
                    await spike_state.update(defuse_remaining=new_defuse)
                    await spike_logic.defuse_success(spike_state)
                else:
                    await spike_state.update(
                        defuse_remaining=new_defuse
                    )
                    await spike_logic.broadcast_state(spike_state)
            
            # Round timer: only counts down when active, not paused, and idle
            if data.round_active and not data.round_paused and data.state == "idle":
                new_round = data.round_remaining - data.time_scale
                if new_round <= 0:
                    await spike_state.update(round_remaining=0, round_active=False)
                    await spike_logic.broadcast_state(spike_state)
                    await spike_logic.notify_backend({"event": "round_expired"})
                else:
                    await spike_state.update(round_remaining=new_round)
                    await spike_logic.broadcast_state(spike_state)
            
            # Refresh the latest state data to print and send to GPIO
            current_data = await spike_state.get_state()
            print_live_line(current_data)
            
            # Update physical indicators for the tick
            gpio_handler.tick(current_data)
            
    except asyncio.CancelledError:
        logger.info("Spike tick loop cancelled.")
    except Exception as e:
        logger.error(f"Error in tick loop: {e}", exc_info=True)
