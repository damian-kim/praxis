from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings
from .contracts import Batch, BatchCreate, EvaluationSuite, EvidenceVerification, Experiment, ExperimentCreate, Health, MetricComparison, PolicyStep, Run, RunComparison, RunCreate, RunDetail, ScenarioInfo, ScenarioResponse, SuiteEvaluation, SuiteEvaluationCreate, WorkerState
from .evidence import verify_evidence_bundle
from .exports import experiment_csv, experiment_junit
from .scenario import discover_scenarios, load_scenario
from .policy_sandbox import PolicyRunnerConfig
from .store import RunStore
from .suites import get_suite, list_suites


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = RunStore(settings.db_path)
    app = FastAPI(title="Praxis Worlds API", version="0.9.0")
    app.state.settings = settings
    app.state.store = store
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def require_scenario(scenario_id: str):
        try:
            path = settings.scenario_path_for(scenario_id)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if not path.is_file():
            raise HTTPException(422, f"Scenario '{scenario_id}' is not installed")
        return path

    @app.get("/health", response_model=Health)
    def health() -> Health:
        store.list_workers()
        seen = store.worker_seen_at()
        queue = store.queue_status()
        return Health(status="ok", database=str(settings.db_path), worker_seen_at=datetime.fromisoformat(seen) if seen else None,
                      **queue)

    @app.get("/api/workers", response_model=list[WorkerState])
    def workers() -> list[WorkerState]:
        return store.list_workers()

    @app.get("/api/suites", response_model=list[EvaluationSuite])
    def suites() -> list[EvaluationSuite]:
        return list_suites()

    @app.get("/api/scenarios", response_model=list[ScenarioInfo])
    def scenarios() -> list[ScenarioInfo]:
        root = settings.worlds_dir or settings.scenario_path.parent.parent
        return [ScenarioInfo(**item) for item in discover_scenarios(root)]

    @app.get("/api/suite-evaluations", response_model=list[SuiteEvaluation])
    def list_suite_evaluations() -> list[SuiteEvaluation]:
        return store.list_suite_evaluations()

    @app.post("/api/suite-evaluations", response_model=SuiteEvaluation, status_code=202)
    def create_suite_evaluation(request: SuiteEvaluationCreate) -> SuiteEvaluation:
        suite = get_suite(request.suite_id)
        if not suite:
            raise HTTPException(422, f"Unknown evaluation suite '{request.suite_id}'")
        for case in suite.cases:
            require_scenario(case.scenario_id)
        if request.engine_id == "deterministic_mock_v1":
            allowed = {"baseline_safe", "baseline_risky"}
            if request.candidate_policy_id not in allowed or request.baseline_policy_id not in allowed:
                raise HTTPException(422, "External policies require the MuJoCo engine")
        return store.create_suite_evaluation(request, suite)

    @app.get("/api/suite-evaluations/{evaluation_id}", response_model=SuiteEvaluation)
    def get_suite_evaluation(evaluation_id: str) -> SuiteEvaluation:
        evaluation = store.get_suite_evaluation(evaluation_id)
        if not evaluation:
            raise HTTPException(404, "Suite evaluation not found")
        return evaluation

    @app.post("/api/suite-evaluations/{evaluation_id}/cancel", response_model=SuiteEvaluation)
    def cancel_suite_evaluation(evaluation_id: str) -> SuiteEvaluation:
        evaluation = store.cancel_suite_evaluation(evaluation_id)
        if not evaluation:
            raise HTTPException(404, "Suite evaluation not found")
        return evaluation

    @app.get("/api/runs", response_model=list[Run])
    def list_runs() -> list[Run]:
        return store.list_runs()

    @app.get("/api/batches", response_model=list[Batch])
    def list_batches() -> list[Batch]:
        return store.list_batches()

    @app.post("/api/batches", response_model=Batch, status_code=202)
    def create_batch(request: BatchCreate) -> Batch:
        require_scenario(request.scenario_id)
        if request.engine_id == "deterministic_mock_v1" and request.policy_id not in {"baseline_safe", "baseline_risky"}:
            raise HTTPException(422, "External policies require the MuJoCo engine")
        return store.create_batch(request)

    @app.get("/api/batches/{batch_id}", response_model=Batch)
    def get_batch(batch_id: str) -> Batch:
        batch = store.get_batch(batch_id)
        if not batch:
            raise HTTPException(404, "Batch not found")
        return batch

    @app.post("/api/batches/{batch_id}/cancel", response_model=Batch)
    def cancel_batch(batch_id: str) -> Batch:
        batch = store.cancel_batch(batch_id)
        if not batch:
            raise HTTPException(404, "Batch not found")
        return batch

    @app.get("/api/experiments", response_model=list[Experiment])
    def list_experiments() -> list[Experiment]:
        return store.list_experiments()

    @app.post("/api/experiments", response_model=Experiment, status_code=202)
    def create_experiment(request: ExperimentCreate) -> Experiment:
        require_scenario(request.scenario_id)
        if request.engine_id == "deterministic_mock_v1":
            allowed = {"baseline_safe", "baseline_risky"}
            if request.candidate_policy_id not in allowed or request.baseline_policy_id not in allowed:
                raise HTTPException(422, "External policies require the MuJoCo engine")
        return store.create_experiment(request)

    @app.get("/api/experiments/{experiment_id}", response_model=Experiment)
    def get_experiment(experiment_id: str) -> Experiment:
        experiment = store.get_experiment(experiment_id)
        if not experiment:
            raise HTTPException(404, "Experiment not found")
        return experiment

    @app.post("/api/experiments/{experiment_id}/cancel", response_model=Experiment)
    def cancel_experiment(experiment_id: str) -> Experiment:
        experiment = store.cancel_experiment(experiment_id)
        if not experiment:
            raise HTTPException(404, "Experiment not found")
        return experiment

    @app.get("/api/experiments/{experiment_id}/export")
    def export_experiment(experiment_id: str, format: str = "json") -> Response:
        experiment = store.get_experiment(experiment_id)
        if not experiment:
            raise HTTPException(404, "Experiment not found")
        if format == "json":
            content, media_type, extension = experiment.model_dump_json(indent=2), "application/json", "json"
        elif format == "csv":
            content, media_type, extension = experiment_csv(experiment), "text/csv", "csv"
        elif format == "junit":
            content, media_type, extension = experiment_junit(experiment), "application/xml", "xml"
        else:
            raise HTTPException(422, "format must be json, csv, or junit")
        return Response(content=content, media_type=media_type,
                        headers={"Content-Disposition": f'attachment; filename="{experiment.id}.{extension}"'})

    @app.post("/api/runs", response_model=Run, status_code=202)
    def create_run(request: RunCreate) -> Run:
        require_scenario(request.scenario_id)
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

    @app.get("/api/policy-runners")
    def policy_runners() -> dict:
        return PolicyRunnerConfig.from_env().diagnostics()

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
        try:
            path = settings.scenario_path_for(scenario_id)
        except ValueError as exc:
            raise HTTPException(404, "Scenario not found") from exc
        if not path.is_file():
            raise HTTPException(404, "Scenario not found")
        return ScenarioResponse(definition=load_scenario(path, seed))

    @app.get("/api/runs/{run_id}/compare/{comparison_id}", response_model=RunComparison)
    def compare_runs(run_id: str, comparison_id: str) -> RunComparison:
        primary, comparison = store.get_run(run_id), store.get_run(comparison_id)
        if not primary or not comparison:
            raise HTTPException(404, "Run not found")
        if (primary.scenario_id, primary.engine_id, primary.seed) != (comparison.scenario_id, comparison.engine_id, comparison.seed):
            raise HTTPException(422, "Run comparisons require the same scenario, engine, and seed")
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
