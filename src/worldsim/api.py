from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings
from .contracts import EvidenceVerification, Health, MetricComparison, PolicyStep, Run, RunComparison, RunCreate, RunDetail, ScenarioResponse
from .evidence import verify_evidence_bundle
from .scenario import load_scenario
from .store import RunStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = RunStore(settings.db_path)
    app = FastAPI(title="Praxis Worlds API", version="0.5.0")
    app.state.settings = settings
    app.state.store = store
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=Health)
    def health() -> Health:
        seen = store.worker_seen_at()
        return Health(status="ok", database=str(settings.db_path), worker_seen_at=datetime.fromisoformat(seen) if seen else None)

    @app.get("/api/runs", response_model=list[Run])
    def list_runs() -> list[Run]:
        return store.list_runs()

    @app.post("/api/runs", response_model=Run, status_code=202)
    def create_run(request: RunCreate) -> Run:
        if request.scenario_id != "warehouse_v0":
            raise HTTPException(422, "Only warehouse_v0 is installed")
        if request.engine_id == "deterministic_mock_v1" and request.policy_id not in {"baseline_safe", "baseline_risky"}:
            raise HTTPException(422, "External policies require the MuJoCo engine")
        return store.create_run(request)

    @app.get("/api/engines")
    def list_engines() -> list[dict]:
        try:
            import mujoco  # noqa: F401
            mujoco_available = True
        except ImportError:
            mujoco_available = False
        return [
            {"id": "mujoco_v1", "name": "MuJoCo 3.11", "available": mujoco_available, "physics": True, "description": "Native rigid-body dynamics and measured contacts"},
            {"id": "deterministic_mock_v1", "name": "Deterministic mock", "available": True, "physics": False, "description": "Fast product-development fixture; synthetic contacts"},
        ]

    @app.get("/api/runs/{run_id}", response_model=RunDetail)
    def get_run(run_id: str) -> RunDetail:
        run = store.get_detail(run_id)
        if not run:
            raise HTTPException(404, "Run not found")
        return run

    @app.post("/api/runs/{run_id}/cancel", response_model=Run)
    def cancel_run(run_id: str) -> Run:
        run = store.request_cancel(run_id)
        if not run:
            raise HTTPException(404, "Run not found")
        return run

    @app.get("/api/runs/{run_id}/policy-trace", response_model=list[PolicyStep])
    def policy_trace(run_id: str) -> list[PolicyStep]:
        if not store.get_run(run_id):
            raise HTTPException(404, "Run not found")
        return [PolicyStep(**step) for step in store.get_policy_steps(run_id)]

    @app.get("/api/runs/{run_id}/evidence/verify", response_model=EvidenceVerification)
    def verify_run_evidence(run_id: str) -> EvidenceVerification:
        if not store.get_run(run_id):
            raise HTTPException(404, "Run not found")
        valid, files_checked, errors = verify_evidence_bundle(settings.data_dir / "runs" / run_id)
        return EvidenceVerification(run_id=run_id, valid=valid, files_checked=files_checked, errors=errors)

    @app.get("/api/scenarios/{scenario_id}", response_model=ScenarioResponse)
    def get_scenario(scenario_id: str, seed: int = 42) -> ScenarioResponse:
        if scenario_id != "warehouse_v0":
            raise HTTPException(404, "Scenario not found")
        return ScenarioResponse(definition=load_scenario(settings.scenario_path, seed))

    @app.get("/api/runs/{run_id}/compare/{comparison_id}", response_model=RunComparison)
    def compare_runs(run_id: str, comparison_id: str) -> RunComparison:
        primary, comparison = store.get_run(run_id), store.get_run(comparison_id)
        if not primary or not comparison:
            raise HTTPException(404, "Run not found")
        keys = ["task_completed", "grasp_qualified", "collisions", "max_contact_force_n", "sim_duration_s"]
        metrics = []
        for key in keys:
            first, second = primary.metrics.get(key), comparison.metrics.get(key)
            delta = None
            if isinstance(first, (int, float)) and not isinstance(first, bool) and isinstance(second, (int, float)) and not isinstance(second, bool):
                delta = float(first - second)
            metrics.append(MetricComparison(metric=key, primary=first, comparison=second, delta=delta))
        return RunComparison(primary_run_id=run_id, comparison_run_id=comparison_id, metrics=metrics)

    return app


app = create_app()
