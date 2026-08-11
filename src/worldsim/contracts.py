from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


RunStatus = Literal[
    "queued", "provisioning", "loading", "running", "finalizing",
    "succeeded", "failed", "cancelled", "interrupted",
]


class RunCreate(BaseModel):
    scenario_id: str = "warehouse_v0"
    policy_id: Literal["baseline_safe", "baseline_risky"] = "baseline_safe"
    engine_id: Literal["deterministic_mock_v1", "mujoco_v1"] = "mujoco_v1"
    seed: int = Field(default=42, ge=0, le=2_147_483_647)


class Run(BaseModel):
    id: str
    scenario_id: str
    policy_id: str
    engine_id: str
    seed: int
    status: RunStatus
    progress: float
    phase: str
    verdict: str | None = None
    error: str | None = None
    metrics: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class Event(BaseModel):
    sequence: int
    kind: str
    message: str
    sim_time: float
    created_at: datetime


class Frame(BaseModel):
    schema_version: str = "2.0"
    sequence: int
    sim_time: float
    robot_x: float
    robot_y: float
    heading: float
    package_x: float
    package_y: float
    carrying: bool
    contact_force: float
    linear_speed_m_s: float | None = None
    angular_speed_rad_s: float | None = None
    shoulder_angle_rad: float | None = None
    elbow_angle_rad: float | None = None
    gripper_width_m: float | None = None
    energy_j: float | None = None


class EvidenceVerification(BaseModel):
    run_id: str
    valid: bool
    files_checked: int
    errors: list[str]


class RunDetail(Run):
    events: list[Event]
    frames: list[Frame]


class Health(BaseModel):
    status: str
    database: str
    worker_seen_at: datetime | None


class ScenarioResponse(BaseModel):
    definition: dict


class MetricComparison(BaseModel):
    metric: str
    primary: float | bool | None
    comparison: float | bool | None
    delta: float | None


class RunComparison(BaseModel):
    primary_run_id: str
    comparison_run_id: str
    metrics: list[MetricComparison]
