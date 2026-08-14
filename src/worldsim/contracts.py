from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field


RunStatus = Literal[
    "queued", "provisioning", "loading", "running", "cancelling", "finalizing",
    "succeeded", "failed", "cancelled", "interrupted",
]


class RunCreate(BaseModel):
    scenario_id: str = "warehouse_v0"
    policy_id: str = Field(default="baseline_safe", min_length=1, max_length=200)
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
    cancel_requested: bool = False
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


class PolicyObservation(BaseModel):
    schema_version: str = "1.0"
    step: int
    sim_time: float
    robot_x: float
    robot_y: float
    heading: float
    linear_speed_m_s: float
    angular_speed_rad_s: float
    package_x: float
    package_y: float
    goal_x: float
    goal_y: float
    carrying: bool
    grasp_qualified: bool
    contact_force_n: float


class PolicyAction(BaseModel):
    schema_version: str = "1.0"
    target_x: float
    target_y: float
    target_heading: float
    shoulder_target_rad: float = -1.02
    elbow_target_rad: float = 1.30
    gripper_target_m: float = .12
    request_grasp: bool = False
    done: bool = False


class PolicyStep(BaseModel):
    sequence: int
    observation: PolicyObservation
    action: PolicyAction
    decision_ms: float


class RunDetail(Run):
    events: list[Event]
    frames: list[Frame]


class Health(BaseModel):
    status: str
    database: str
    worker_seen_at: datetime | None
    active_workers: int = 0
    active_runs: int = 0
    queued_runs: int = 0


class ScenarioResponse(BaseModel):
    definition: dict


class ScenarioInfo(BaseModel):
    id: str
    name: str
    objective: str
    schema_version: str


class MetricComparison(BaseModel):
    metric: str
    primary: float | bool | None
    comparison: float | bool | None
    delta: float | None


class RunComparison(BaseModel):
    primary_run_id: str
    comparison_run_id: str
    metrics: list[MetricComparison]


class BatchCreate(BaseModel):
    scenario_id: str = "warehouse_v0"
    policy_id: str = Field(default="baseline_safe", min_length=1, max_length=200)
    engine_id: Literal["deterministic_mock_v1", "mujoco_v1"] = "mujoco_v1"
    seeds: list[int] = Field(min_length=1, max_length=50)


class Batch(BaseModel):
    id: str
    scenario_id: str
    policy_id: str
    engine_id: str
    seeds: list[int]
    created_at: datetime
    counts: dict[str, int]
    pass_rate: float | None
    runs: list[Run]


class GateConfig(BaseModel):
    min_candidate_pass_rate: float = Field(default=.90, ge=0, le=1)
    max_pass_rate_drop: float = Field(default=0, ge=0, le=1)
    max_mean_collision_increase: float = Field(default=0, ge=0)
    max_mean_force_increase_n: float = Field(default=0, ge=0)
    max_mean_duration_increase_s: float = Field(default=2, ge=0)


class ExperimentCreate(BaseModel):
    scenario_id: str = "warehouse_v0"
    candidate_policy_id: str = Field(min_length=1, max_length=200)
    baseline_policy_id: str = Field(default="baseline_safe", min_length=1, max_length=200)
    engine_id: Literal["deterministic_mock_v1", "mujoco_v1"] = "mujoco_v1"
    seeds: list[int] = Field(min_length=1, max_length=50)
    gates: GateConfig = Field(default_factory=GateConfig)


class SeedComparison(BaseModel):
    seed: int
    candidate_run: Run
    baseline_run: Run
    metric_deltas: dict[str, float | None]
    failure_reasons: list[str]


class Experiment(BaseModel):
    id: str
    scenario_id: str
    candidate_policy_id: str
    baseline_policy_id: str
    engine_id: str
    seeds: list[int]
    candidate_batch_id: str
    baseline_batch_id: str
    gates: GateConfig
    created_at: datetime
    status: Literal["running", "complete"]
    verdict: Literal["pending", "pass", "fail"]
    summary: dict
    gate_results: list[dict]
    pairs: list[SeedComparison]


class EvaluationSuite(BaseModel):
    id: str
    name: str
    description: str
    cases: list["SuiteCase"]
    purpose: str

    @computed_field
    def pair_count(self) -> int:
        return sum(len(case.seeds) for case in self.cases)

    @computed_field
    @property
    def seeds(self) -> list[int]:
        """Flattened compatibility view; suite execution still preserves scenario boundaries."""
        return [seed for case in self.cases for seed in case.seeds]

    @computed_field
    @property
    def scenario_id(self) -> str:
        return self.cases[0].scenario_id if len(self.cases) == 1 else "multiple"


class SuiteCase(BaseModel):
    scenario_id: str
    seeds: list[int] = Field(min_length=1, max_length=50)


class SuiteEvaluationCreate(BaseModel):
    suite_id: str
    candidate_policy_id: str = Field(min_length=1, max_length=200)
    baseline_policy_id: str = Field(default="baseline_safe", min_length=1, max_length=200)
    engine_id: Literal["deterministic_mock_v1", "mujoco_v1"] = "mujoco_v1"
    gates: GateConfig = Field(default_factory=GateConfig)


class SuiteEvaluation(BaseModel):
    id: str
    suite_id: str
    candidate_policy_id: str
    baseline_policy_id: str
    engine_id: str
    experiment_ids: list[str]
    created_at: datetime
    status: Literal["running", "complete"]
    verdict: Literal["pending", "pass", "fail"]
    completed_pairs: int
    total_pairs: int
    scenario_results: list[Experiment]


class WorkerState(BaseModel):
    id: str
    process_id: int
    max_active_runs: int = 1
    started_at: datetime
    last_seen_at: datetime
    current_run_id: str | None = None
