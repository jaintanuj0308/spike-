# spike_state.py - Dataclass and thread-safe wrapper for the Spike state machine
import asyncio
from dataclasses import dataclass, asdict
from typing import Optional
import config

@dataclass
class StateData:
    state: str = "idle"               # idle | planting | planted | defusing | defused | exploded
    plant_remaining: int = config.PLANT_TIME
    spike_remaining: int = config.SPIKE_TIME
    defuse_remaining: int = config.DEFUSE_TIME
    spike_paused: bool = False
    planter_id: Optional[str] = None  # Attacker player ID
    defuser_id: Optional[str] = None  # Defender player ID
    round_remaining: int = config.ROUND_TIME
    round_active: bool = False
    round_paused: bool = False
    time_scale: float = 1.0

class SpikeState:
    def __init__(self):
        self._data = StateData()
        self._lock = asyncio.Lock()

    async def get_state(self) -> StateData:
        async with self._lock:
            return StateData(
                state=self._data.state,
                plant_remaining=self._data.plant_remaining,
                spike_remaining=self._data.spike_remaining,
                defuse_remaining=self._data.defuse_remaining,
                spike_paused=self._data.spike_paused,
                planter_id=self._data.planter_id,
                defuser_id=self._data.defuser_id,
                round_remaining=self._data.round_remaining,
                round_active=self._data.round_active,
                round_paused=self._data.round_paused,
                time_scale=self._data.time_scale
            )

    async def update(self, **kwargs):
        async with self._lock:
            for key, val in kwargs.items():
                if hasattr(self._data, key):
                    setattr(self._data, key, val)
                else:
                    raise AttributeError(f"StateData has no attribute {key}")

    async def to_dict(self) -> dict:
        async with self._lock:
            return asdict(self._data)
            
    async def reset(self):
        async with self._lock:
            self._data.state = "idle"
            self._data.plant_remaining = config.PLANT_TIME
            self._data.spike_remaining = config.SPIKE_TIME
            self._data.spike_paused = False
            self._data.defuse_remaining = config.DEFUSE_TIME
            self._data.planter_id = None
            self._data.defuser_id = None
            self._data.round_remaining = config.ROUND_TIME
            self._data.round_active = False
            self._data.round_paused = False
            self._data.time_scale = 1.0
