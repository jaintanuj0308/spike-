# routes.py - FastAPI HTTP API Route Handlers
from fastapi import APIRouter, Depends, HTTPException
from spike_state import SpikeState
import spike_logic

# Standard factory to get injected state
def get_state() -> SpikeState:
    raise NotImplementedError("State dependency override must be registered")

router = APIRouter()

@router.get("/status")
async def get_status(state: SpikeState = Depends(get_state)):
    """Returns the current SpikeState as a JSON payload."""
    return await state.to_dict()

@router.post("/reset")
async def reset(state: SpikeState = Depends(get_state)):
    """Resets the round to IDLE state."""
    await spike_logic.reset_round(state)
    return {"status": "ok", "message": "Round reset to IDLE"}

@router.post("/kill/{player_id}")
async def kill_player(player_id: str, state: SpikeState = Depends(get_state)):
    """Triggers the on_player_killed handler for a player ID."""
    triggered = await spike_logic.on_player_killed(state, player_id)
    if not triggered:
        return {"status": "ignored", "message": f"Kill event ignored for player '{player_id}'"}
    return {"status": "ok", "message": f"Player '{player_id}' killed"}

@router.post("/plant/{player_id}")
async def force_plant(player_id: str, state: SpikeState = Depends(get_state)):
    """Manually triggers the start_plant handler."""
    triggered = await spike_logic.start_plant(state, player_id)
    if not triggered:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot start planting from current state"
        )
    return {"status": "ok", "message": f"Planting started by player '{player_id}'"}

@router.post("/defuse/{player_id}")
async def force_defuse(player_id: str, state: SpikeState = Depends(get_state)):
    """Manually triggers the start_defuse handler."""
    triggered = await spike_logic.start_defuse(state, player_id)
    if not triggered:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot start defusing from current state"
        )
    return {"status": "ok", "message": f"Defusing started by player '{player_id}'"}
