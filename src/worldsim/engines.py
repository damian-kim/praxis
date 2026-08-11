from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .contracts import Run
from .store import RunStore


@dataclass(frozen=True)
class EngineCapabilities:
    engine_id: str
    physics: bool
    rigid_body_contacts: bool
    camera_rendering: bool
    deterministic_replay: bool


class SimulationEngine(Protocol):
    capabilities: EngineCapabilities

    def execute(self, store: RunStore, run: Run, evidence_root: Path, frame_delay: float) -> dict: ...


MOCK_CAPABILITIES = EngineCapabilities(
    engine_id="deterministic_mock_v1",
    physics=False,
    rigid_body_contacts=False,
    camera_rendering=False,
    deterministic_replay=True,
)


class DeterministicMockEngine:
    capabilities = MOCK_CAPABILITIES

    def __init__(self, scenario_path: Path):
        self.scenario_path = scenario_path

    def execute(self, store: RunStore, run: Run, evidence_root: Path, frame_delay: float) -> dict:
        from .simulator import execute_mock_run
        return execute_mock_run(store, run, evidence_root, frame_delay, self.scenario_path)


def resolve_engine(engine_id: str, scenario_path: Path) -> SimulationEngine:
    if engine_id == MOCK_CAPABILITIES.engine_id:
        return DeterministicMockEngine(scenario_path)
    if engine_id == "mujoco_v1":
        try:
            from .mujoco_engine import MujocoEngine
        except ImportError as exc:
            raise RuntimeError("MuJoCo is not installed. Run `python -m pip install -e .[physics]`.") from exc
        return MujocoEngine(scenario_path)
    raise ValueError(f"Unknown simulation engine: {engine_id}")
