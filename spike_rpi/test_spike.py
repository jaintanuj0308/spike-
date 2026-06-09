# test_spike.py - Interactive cross-platform terminal game-loop simulation
import asyncio
import sys
import logging
from spike_state import SpikeState
import spike_logic
from tick import tick_loop
import config

# Configure logging to warnings-only for clean CLI experience
logging.basicConfig(level=logging.WARNING)

# Cross-platform non-blocking key reader
if sys.platform == 'win32':
    import msvcrt
    def read_keyboard_key() -> str:
        if msvcrt.kbhit():
            try:
                ch = msvcrt.getch()
                return ch.decode('utf-8').lower()
            except Exception:
                return ""
        return ""
else:
    import select
    import termios
    import tty
    def read_keyboard_key() -> str:
        if select.select([sys.stdin], [], [], 0)[0]:
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            return ch.lower()
        return ""


async def keyboard_input_loop(state: SpikeState):
    """Listens for keypress events to simulate USB plug/unplug and other sensor triggers."""
    print("==================================================")
    print("           SPIKE INTERACTIVE TESTER")
    print("==================================================")
    print("  Hotkeys (Press key directly, no Enter needed):")
    print("  [P] - Insert Attacker USB (Starts Planting)")
    print("  [A] - Pull Attacker USB   (Attacker Killed)")
    print("  [D] - Insert Defender USB (Starts Defusing)")
    print("  [S] - Pull Defender USB   (Defender Killed)")
    print("  [E] - Force Explosion")
    print("  [R] - Reset Round to IDLE")
    print("  [G] - Start Round (round_start)")
    print("  [H] - End Round   (round_end)")
    print("  [1] - Set Time Scale x1")
    print("  [2] - Set Time Scale x2")
    print("  [3] - Set Time Scale x5")
    print("  [Q] - Quit Tester")
    print("==================================================")
    sys.stdout.flush()

    while True:
        # Check keyboard every 50ms
        await asyncio.sleep(0.05)
        key = read_keyboard_key()
        
        if not key:
            continue

        if key == 'q':
            print("\nExiting interactive tester...")
            break
            
        elif key == 'p':
            print("\n[EVENT] Inserting Attacker USB (A1)...")
            await spike_logic.start_plant(state, "A1")
            
        elif key == 'a':
            print("\n[EVENT] Pulling Attacker USB (A1)...")
            await spike_logic.on_player_killed(state, "A1")
            
        elif key == 'd':
            print("\n[EVENT] Inserting Defender USB (D1)...")
            await spike_logic.start_defuse(state, "D1")
            
        elif key == 's':
            print("\n[EVENT] Pulling Defender USB (D1)...")
            await spike_logic.on_player_killed(state, "D1")
            
        elif key == 'e':
            print("\n[EVENT] Triggering Force Explosion...")
            await spike_logic.explode(state)
            
        elif key == 'r':
            print("\n[EVENT] Resetting round...")
            await spike_logic.reset_round(state)

        elif key == 'g':
            print("\n[EVENT] Starting round...")
            await spike_logic.start_round(state)

        elif key == 'h':
            print("\n[EVENT] Ending round...")
            await spike_logic.reset_round(state)

        elif key == '1':
            print("\n[EVENT] Set time_scale = 1.0")
            await state.update(time_scale=1.0)

        elif key == '2':
            print("\n[EVENT] Set time_scale = 2.0")
            await state.update(time_scale=2.0)

        elif key == '3':
            print("\n[EVENT] Set time_scale = 5.0")
            await state.update(time_scale=5.0)


async def main():
    state = SpikeState()
    
    # Run the core 1s ticking loop alongside the keyboard listener
    tick_task = asyncio.create_task(tick_loop(state))
    input_task = asyncio.create_task(keyboard_input_loop(state))
    
    # Wait for the user to quit (input_task finishes)
    done, pending = await asyncio.wait(
        [tick_task, input_task],
        return_when=asyncio.FIRST_COMPLETED
    )
    
    # Clean up pending tasks
    for task in pending:
        task.cancel()
        
    await asyncio.gather(*pending, return_exceptions=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting interactive tester...")
