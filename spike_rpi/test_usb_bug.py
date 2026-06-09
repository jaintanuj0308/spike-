import asyncio, sys, os

# Ensure project root is on sys.path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

from spike_state import SpikeState
from usb_monitor import USBMonitor
from tick import tick_loop

async def verify():
    state = SpikeState()
    monitor = USBMonitor(state)
    # Simulate attacker USB insert when idle
    monitor.mock_trigger_insert('A1')
    # Run tick loop for a short period to process planting
    tick_task = asyncio.create_task(tick_loop(state))
    await asyncio.sleep(2)  # allow planting to start
    data = await state.get_state()
    print('State after insert:', data.state)
    print('Plant remaining:', data.plant_remaining)
    # Clean up
    tick_task.cancel()
    try:
        await tick_task
    except asyncio.CancelledError:
        pass

if __name__ == '__main__':
    asyncio.run(verify())
