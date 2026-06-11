# test_scenario.py - Automated End-to-End State Machine Scenario Test Runner
import asyncio
import sys
import logging
from spike_state import SpikeState, StateData
import spike_logic
import config

# Set logging level to warning for clean test output
logging.basicConfig(level=logging.WARNING)

async def simulate_tick(state: SpikeState):
    """
    Simulates a single 1-second game tick instantly (without sleep)
    to verify timer logic and state transitions in automated testing.
    """
    data = await state.get_state()
    if data.state == "planting":
        new_plant = data.plant_remaining - 1
        if new_plant <= 0:
            await spike_logic.spike_planted(state)
        else:
            await state.update(plant_remaining=new_plant)
            
    elif data.state == "planted":
        new_spike = data.spike_remaining - 1
        if new_spike <= 0:
            await spike_logic.explode(state)
        else:
            await state.update(spike_remaining=new_spike)
            
    elif data.state == "defusing":
        # Spike timer paused; only defuse timer counts down
        new_defuse = data.defuse_remaining - 1
        if new_defuse <= 0:
            await spike_logic.defuse_success(state)
        else:
            await state.update(defuse_remaining=new_defuse)

    # Round timer: only counts down when active, not paused, and idle
    if data.round_active and not data.round_paused and data.state == "idle":
        new_round = data.round_remaining - data.time_scale
        if new_round <= 0:
            await state.update(round_remaining=0, round_active=False)
        else:
            await state.update(round_remaining=new_round)


# =====================================================================
# TEST CASES
# =====================================================================

async def test_scenario_1_plant_and_defuse():
    """SCENARIO 1: Complete Plant -> Defuse victory sequence."""
    print("\n--- Running Scenario 1: Plant -> Defuse Success ---")
    state = SpikeState()
    
    # 1. Start Planting (Must be attacker prefix e.g., 'A1')
    success = await spike_logic.start_plant(state, "A1")
    assert success, "Should start planting"
    data = await state.get_state()
    assert data.state == "planting"
    assert data.planter_id == "A1"
    
    # 2. Fast forward planting duration
    for _ in range(config.PLANT_TIME):
        await simulate_tick(state)
        
    data = await state.get_state()
    assert data.state == "planted", "Spike should transition to PLANTED after plant duration"
    assert data.spike_remaining == config.SPIKE_TIME
    assert data.defuse_remaining == config.DEFUSE_TIME
    
    # 3. Start Defusing (Must be defender prefix e.g., 'D1')
    success = await spike_logic.start_defuse(state, "D1")
    assert success, "Should start defusal"
    data = await state.get_state()
    assert data.state == "defusing"
    assert data.defuser_id == "D1"
    
    # 4. Fast forward defuse duration
    # Temporarily adjust configuration durations to ensure defusal success is possible.
    original_defuse = config.DEFUSE_TIME
    config.DEFUSE_TIME = 30  # Defuse takes 30s, spike takes 40s
    await state.update(defuse_remaining=30)
    
    for _ in range(30):
        await simulate_tick(state)
        
    data = await state.get_state()
    assert data.state == "defused", "Spike should be DEFUSED"
    assert data.defuse_remaining == 0
    assert data.spike_remaining > 0, "Spike should not have exploded"
    
    # Restore config
    config.DEFUSE_TIME = original_defuse
    print("[PASS] Scenario 1: Passed!")


async def test_scenario_2_plant_and_explode():
    """SCENARIO 2: Complete Plant -> Detonation sequence."""
    print("\n--- Running Scenario 2: Plant -> Explosion ---")
    state = SpikeState()
    
    # 1. Start Planting
    await spike_logic.start_plant(state, "A1")
    for _ in range(config.PLANT_TIME):
        await simulate_tick(state)
        
    data = await state.get_state()
    assert data.state == "planted"
    
    # 2. Let spike timer expire
    for _ in range(config.SPIKE_TIME):
        await simulate_tick(state)
        
    data = await state.get_state()
    assert data.state == "exploded", "Spike should transition to EXPLODED"
    assert data.spike_remaining == 0
    print("[PASS] Scenario 2: Passed!")


async def test_scenario_3_planter_killed():
    """SCENARIO 3: Planting is interrupted by planter being killed."""
    print("\n--- Running Scenario 3: Planter Killed -> Return to Idle ---")
    state = SpikeState()
    
    # 1. Start Planting
    await spike_logic.start_plant(state, "A1")
    
    # 2. Tick part way
    for _ in range(10):
        await simulate_tick(state)
        
    data = await state.get_state()
    assert data.state == "planting"
    assert data.plant_remaining == config.PLANT_TIME - 10
    
    # 3. Kill planter
    success = await spike_logic.on_player_killed(state, "A1")
    assert success, "Should trigger player killed logic"
    
    data = await state.get_state()
    assert data.state == "idle", "Should return to IDLE"
    assert data.plant_remaining == config.PLANT_TIME, "Plant remaining should reset"
    assert data.planter_id is None
    print("[PASS] Scenario 3: Passed!")


async def test_scenario_4_defuser_killed_resume():
    """SCENARIO 4: Defusal is interrupted, resumes progress, and succeeds."""
    print("\n--- Running Scenario 4: Defuser Killed -> Resume -> Success ---")
    state = SpikeState()
    
    # Configure custom parameters for deterministic testing:
    original_spike = config.SPIKE_TIME
    original_defuse = config.DEFUSE_TIME
    config.SPIKE_TIME = 80
    config.DEFUSE_TIME = 60
    
    # Reset state timers
    await state.reset()
    await state.update(
        spike_remaining=80,
        defuse_remaining=60
    )
    
    # 1. Plant
    await spike_logic.start_plant(state, "A1")
    for _ in range(config.PLANT_TIME):
        await simulate_tick(state)
        
    data = await state.get_state()
    assert data.state == "planted"
    assert data.spike_remaining == 80
    assert data.defuse_remaining == 60
    
    # 2. Start Defusing
    await spike_logic.start_defuse(state, "D1")
    
    # 3. Defuse for 20 seconds
    for _ in range(20):
        await simulate_tick(state)
        
    data = await state.get_state()
    assert data.state == "defusing"
    assert data.defuse_remaining == 40, "Defuse remaining should be 40s (60 - 20)"
    assert data.spike_remaining == 80, "Spike remaining should be unchanged (80) during defuse"
    
    # 4. Defuser D1 is killed/removed
    success = await spike_logic.on_player_killed(state, "D1")
    assert success
    
    data = await state.get_state()
    assert data.state == "planted", "Should go back to PLANTED state"
    assert data.defuser_id is None
    assert data.defuse_remaining == 40, "Defuse progress must be saved (not reset)"
    
    # 5. Let spike tick for 10 seconds while planter is dead
    for _ in range(10):
        await simulate_tick(state)
        
    data = await state.get_state()
    assert data.state == "planted"
    assert data.defuse_remaining == 40, "Defuse remaining should remain paused at 40s"
    assert data.spike_remaining == 70, "Spike countdown must continue to decrement"
    
    # 6. A new defuser D2 starts defusing
    success = await spike_logic.start_defuse(state, "D2")
    assert success
    
    # 7. Defuse for remaining 40 seconds to finish
    for _ in range(40):
        await simulate_tick(state)
        
    data = await state.get_state()
    assert data.state == "defused"
    assert data.defuse_remaining == 0
    assert data.spike_remaining == 70, f"Spike should have 70 seconds left (got {data.spike_remaining}s)"
    
    # Restore configs
    config.SPIKE_TIME = original_spike
    config.DEFUSE_TIME = original_defuse
    print("[PASS] Scenario 4: Passed!")

async def test_scenario_5_round_timer_countdown():
    """SCENARIO 5: Round timer counts down each tick while idle and active."""
    print("\n--- Running Scenario 5: Round Timer Countdown ---")
    state = SpikeState()

    # Start the round
    await spike_logic.start_round(state)
    data = await state.get_state()
    assert data.round_active is True
    assert data.round_paused is False
    assert data.round_remaining == config.ROUND_TIME

    # Tick 10 times
    for _ in range(10):
        await simulate_tick(state)

    data = await state.get_state()
    assert data.round_remaining == config.ROUND_TIME - 10, (
        f"Round remaining should be {config.ROUND_TIME - 10}, got {data.round_remaining}"
    )
    assert data.round_active is True
    print("[PASS] Scenario 5: Passed!")


async def test_scenario_6_round_pauses_during_planting():
    """SCENARIO 6: Round timer pauses when planting starts."""
    print("\n--- Running Scenario 6: Round Pauses During Planting ---")
    state = SpikeState()

    # Start round and tick 5 times
    await spike_logic.start_round(state)
    for _ in range(5):
        await simulate_tick(state)

    data = await state.get_state()
    round_before_plant = data.round_remaining
    assert round_before_plant == config.ROUND_TIME - 5

    # Start planting — round_paused should become True
    await spike_logic.start_plant(state, "A1")
    data = await state.get_state()
    assert data.state == "planting"
    assert data.round_paused is True, "Round should be paused while planting"

    # Tick 10 more times (planting ticks, but round should NOT decrement)
    for _ in range(10):
        await simulate_tick(state)

    data = await state.get_state()
    assert data.round_remaining == round_before_plant, (
        f"Round remaining should stay at {round_before_plant} during planting, got {data.round_remaining}"
    )
    print("[PASS] Scenario 6: Passed!")


async def test_scenario_7_round_resumes_when_planter_killed():
    """SCENARIO 7: Round timer resumes when planter is killed and state returns to idle."""
    print("\n--- Running Scenario 7: Round Resumes After Planter Killed ---")
    state = SpikeState()

    # Start round and tick 5 times
    await spike_logic.start_round(state)
    for _ in range(5):
        await simulate_tick(state)

    data = await state.get_state()
    round_before_plant = data.round_remaining

    # Start planting
    await spike_logic.start_plant(state, "A1")
    data = await state.get_state()
    assert data.round_paused is True

    # Tick 10 times during planting
    for _ in range(10):
        await simulate_tick(state)

    # Kill the planter — should return to idle with round_paused=False
    await spike_logic.on_player_killed(state, "A1")
    data = await state.get_state()
    assert data.state == "idle"
    assert data.round_paused is False, "Round should resume after planter killed"
    assert data.round_remaining == round_before_plant, (
        "Round remaining should not have changed during planting"
    )

    # Tick 5 more times — round timer should decrement again
    for _ in range(5):
        await simulate_tick(state)

    data = await state.get_state()
    assert data.round_remaining == round_before_plant - 5, (
        f"Round remaining should be {round_before_plant - 5}, got {data.round_remaining}"
    )
    print("[PASS] Scenario 7: Passed!")


async def test_scenario_8_spike_timer_freezes_during_defuse():
    """SCENARIO 8: Spike timer freezes during defuse and resumes when defuser killed."""
    print("\n--- Running Scenario 8: Spike Timer Freeze/Resume During Defuse ---")
    state = SpikeState()

    original_spike = config.SPIKE_TIME
    original_defuse = config.DEFUSE_TIME
    config.SPIKE_TIME = 100
    config.DEFUSE_TIME = 60
    await state.reset()
    await state.update(spike_remaining=100, defuse_remaining=60)

    # Plant
    await spike_logic.start_plant(state, "A1")
    for _ in range(config.PLANT_TIME):
        await simulate_tick(state)

    data = await state.get_state()
    assert data.state == "planted"
    spike_after_plant = data.spike_remaining

    # Tick spike for 20 seconds
    for _ in range(20):
        await simulate_tick(state)

    data = await state.get_state()
    assert data.spike_remaining == spike_after_plant - 20
    spike_before_defuse = data.spike_remaining

    # Start defusing — spike timer should freeze
    await spike_logic.start_defuse(state, "D1")
    data = await state.get_state()
    assert data.state == "defusing"
    assert data.spike_paused is True

    # Tick 15 times during defuse — spike should NOT change
    for _ in range(15):
        await simulate_tick(state)

    data = await state.get_state()
    assert data.spike_remaining == spike_before_defuse, (
        f"Spike should be frozen at {spike_before_defuse}, got {data.spike_remaining}"
    )
    assert data.defuse_remaining == 60 - 15, (
        f"Defuse should be 45, got {data.defuse_remaining}"
    )

    # Kill defuser — spike timer should resume
    await spike_logic.on_player_killed(state, "D1")
    data = await state.get_state()
    assert data.state == "planted"
    assert data.spike_paused is False, "Spike timer should resume after defuser killed"

    # Tick 10 more — spike should decrement again
    for _ in range(10):
        await simulate_tick(state)

    data = await state.get_state()
    assert data.spike_remaining == spike_before_defuse - 10, (
        f"Spike should be {spike_before_defuse - 10}, got {data.spike_remaining}"
    )

    config.SPIKE_TIME = original_spike
    config.DEFUSE_TIME = original_defuse
    print("[PASS] Scenario 8: Passed!")


async def test_scenario_9_multi_round_flow():
    """SCENARIO 9: Multi-round sequence (Round 1: Defusal Victory -> Reset -> Round 2: Detonation Victory -> Reset)."""
    print("\n--- Running Scenario 9: Multi-Round Flow (Round 1: Defuse -> Reset -> Round 2: Explode) ---")
    state = SpikeState()
    
    # --- ROUND 1 ---
    await spike_logic.start_round(state)
    await spike_logic.start_plant(state, "A1")
    for _ in range(config.PLANT_TIME):
        await simulate_tick(state)
    data = await state.get_state()
    assert data.state == "planted"
    
    # Start defusing (using the previously-failing A1 default player to verify the role fix!)
    # We pass skip_role_check=True because the USB monitor does this now
    success = await spike_logic.start_defuse(state, "A1", skip_role_check=True)
    assert success, "Should start defusal for A1 with skip_role_check=True"
    
    # Fast forward defusal
    original_defuse = config.DEFUSE_TIME
    config.DEFUSE_TIME = 10
    await state.update(defuse_remaining=10)
    for _ in range(10):
        await simulate_tick(state)
        
    data = await state.get_state()
    assert data.state == "defused", "Round 1 should end in defused state"
    
    # Reset Round 1
    await spike_logic.reset_round(state)
    data = await state.get_state()
    assert data.state == "idle", "RPi should go back to IDLE after reset_round"
    
    # --- ROUND 2 ---
    await spike_logic.start_round(state)
    await spike_logic.start_plant(state, "A1")
    for _ in range(config.PLANT_TIME):
        await simulate_tick(state)
    data = await state.get_state()
    assert data.state == "planted"
    
    # Let it explode
    for _ in range(config.SPIKE_TIME):
        await simulate_tick(state)
        
    data = await state.get_state()
    assert data.state == "exploded", "Round 2 should end in exploded state"
    
    # Reset Round 2
    await spike_logic.reset_round(state)
    data = await state.get_state()
    assert data.state == "idle", "RPi should go back to IDLE after reset_round"
    
    # Restore config
    config.DEFUSE_TIME = original_defuse
    print("[PASS] Scenario 9: Passed!")


async def main():
    print("=======================================")
    print("RUNNING SPIKE STATE MACHINE AUTOMATED TESTS")
    print("=======================================")
    
    try:
        await test_scenario_1_plant_and_defuse()
        await test_scenario_2_plant_and_explode()
        await test_scenario_3_planter_killed()
        await test_scenario_4_defuser_killed_resume()
        await test_scenario_5_round_timer_countdown()
        await test_scenario_6_round_pauses_during_planting()
        await test_scenario_7_round_resumes_when_planter_killed()
        await test_scenario_8_spike_timer_freezes_during_defuse()
        await test_scenario_9_multi_round_flow()
        print("\n=======================================")
        print("ALL SCENARIO TESTS PASSED SUCCESSFULLY!")
        print("=======================================")
    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILURE DETECTED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] UNEXPECTED ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
