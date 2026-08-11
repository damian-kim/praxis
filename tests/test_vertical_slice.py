from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from worldsim.api import create_app
from worldsim.config import Settings
from worldsim.contracts import RunCreate
from worldsim.simulator import execute_mock_run
from worldsim.scenario import load_scenario
from worldsim.evidence import verify_evidence_bundle
from worldsim.policy import EpisodeContext, load_policy
from worldsim.contracts import PolicyObservation
from worldsim.policy_runtime import IsolatedPolicyClient, PolicyRuntimeError
from worldsim.cli import parse_seeds
from worldsim.store import RunStore


def settings_for(tmp_path: Path) -> Settings:
    scenario_path = Path(__file__).resolve().parents[1] / "worlds" / "warehouse_v0" / "scenario.json"
    return Settings(tmp_path, tmp_path / "worldsim.db", scenario_path)


def test_api_creates_durable_queued_run(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/runs", json={"policy_id": "baseline_safe", "seed": 7})
        assert response.status_code == 202
        run_id = response.json()["id"]

    # A new app process can recover the same run from SQLite.
    with TestClient(create_app(settings)) as restarted_client:
        recovered = restarted_client.get(f"/api/runs/{run_id}")
        assert recovered.status_code == 200
        assert recovered.json()["status"] == "queued"


def test_safe_policy_completes_and_writes_evidence(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    store = RunStore(settings.db_path)
    queued = store.create_run(RunCreate(policy_id="baseline_safe", engine_id="deterministic_mock_v1", seed=42))
    claimed = store.claim_next()
    assert claimed and claimed.id == queued.id

    evidence = execute_mock_run(store, claimed, tmp_path, frame_delay=0)
    complete = store.get_detail(queued.id)

    assert complete is not None
    assert complete.status == "succeeded"
    assert complete.verdict == "pass"
    assert len(complete.frames) == 49
    assert evidence["metrics"]["collisions"] == 0
    written = json.loads((tmp_path / "runs" / queued.id / "evidence.json").read_text())
    assert written["schema_version"] == "2.0"
    assert (tmp_path / "runs" / queued.id / "manifest.json").exists()
    assert verify_evidence_bundle(tmp_path / "runs" / queued.id)[0] is True


def test_risky_policy_fails_contact_limit(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    store = RunStore(settings.db_path)
    store.create_run(RunCreate(policy_id="baseline_risky", engine_id="deterministic_mock_v1", seed=3))
    claimed = store.claim_next()
    assert claimed

    execute_mock_run(store, claimed, tmp_path, frame_delay=0)
    complete = store.get_detail(claimed.id)

    assert complete is not None
    assert complete.status == "failed"
    assert complete.metrics["collisions"] == 1
    assert complete.metrics["max_contact_force_n"] > 100
    failed_checks = [check["id"] for check in complete.metrics["checks"] if not check["passed"]]
    assert "max_collisions" in failed_checks
    assert "max_contact_force_n" in failed_checks


def test_seeded_scenario_variation_is_reproducible(tmp_path: Path) -> None:
    path = settings_for(tmp_path).scenario_path
    first = load_scenario(path, 123)
    repeated = load_scenario(path, 123)
    different = load_scenario(path, 124)

    assert first == repeated
    assert first["task"]["package_spawn"] != different["task"]["package_spawn"]
    assert first["limits"]["max_contact_force_n"]["calibration_status"] == "synthetic"


def test_scenario_and_comparison_api(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    store = RunStore(settings.db_path)
    safe = store.create_run(RunCreate(policy_id="baseline_safe", engine_id="deterministic_mock_v1", seed=9))
    safe_claim = store.claim_next()
    assert safe_claim
    execute_mock_run(store, safe_claim, tmp_path, frame_delay=0, scenario_path=settings.scenario_path)
    risky = store.create_run(RunCreate(policy_id="baseline_risky", engine_id="deterministic_mock_v1", seed=9))
    risky_claim = store.claim_next()
    assert risky_claim
    execute_mock_run(store, risky_claim, tmp_path, frame_delay=0, scenario_path=settings.scenario_path)

    with TestClient(create_app(settings)) as client:
        scenario = client.get("/api/scenarios/warehouse_v0?seed=9")
        comparison = client.get(f"/api/runs/{risky.id}/compare/{safe.id}")
        verification = client.get(f"/api/runs/{safe.id}/evidence/verify")

    assert scenario.status_code == 200
    assert scenario.json()["definition"]["episode_seed"] == 9
    assert comparison.status_code == 200
    collision = next(metric for metric in comparison.json()["metrics"] if metric["metric"] == "collisions")
    assert collision["delta"] == 1
    assert verification.json()["valid"] is True


def test_mujoco_engine_records_real_contact_evidence(tmp_path: Path) -> None:
    from worldsim.mujoco_engine import MujocoEngine

    settings = settings_for(tmp_path)
    store = RunStore(settings.db_path)
    store.create_run(RunCreate(policy_id="baseline_risky", engine_id="mujoco_v1", seed=21))
    claimed = store.claim_next()
    assert claimed

    evidence = MujocoEngine(settings.scenario_path).execute(store, claimed, tmp_path, frame_delay=0)

    assert evidence["engine"]["physics"] is True
    assert evidence["engine"]["rigid_body_contacts"] is True
    assert evidence["metrics"]["measured_contact_samples"] > 0
    assert evidence["metrics"]["max_contact_force_n"] > 0
    assert (tmp_path / "runs" / claimed.id / "model.xml").exists()
    assert evidence["frame_schema_version"] == "2.0"
    assert evidence["trajectory"][-1]["energy_j"] > 0
    assert evidence["trajectory"][-1]["shoulder_angle_rad"] is not None
    valid, checked, errors = verify_evidence_bundle(tmp_path / "runs" / claimed.id)
    assert valid is True and checked == 3 and errors == []


def test_evidence_verifier_detects_tampering(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    store = RunStore(settings.db_path)
    store.create_run(RunCreate(policy_id="baseline_safe", engine_id="deterministic_mock_v1", seed=5))
    claimed = store.claim_next()
    assert claimed
    execute_mock_run(store, claimed, tmp_path, frame_delay=0, scenario_path=settings.scenario_path)
    evidence_path = tmp_path / "runs" / claimed.id / "evidence.json"
    evidence_path.write_text(evidence_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    valid, checked, errors = verify_evidence_bundle(evidence_path.parent)
    assert valid is False
    assert checked == 1
    assert "evidence.json hash mismatch" in errors


def test_existing_frame_database_migrates_without_data_loss(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE frames (run_id TEXT NOT NULL, sequence INTEGER NOT NULL, sim_time REAL NOT NULL, robot_x REAL NOT NULL, robot_y REAL NOT NULL, heading REAL NOT NULL, package_x REAL NOT NULL, package_y REAL NOT NULL, carrying INTEGER NOT NULL, contact_force REAL NOT NULL, PRIMARY KEY (run_id, sequence))")
        db.execute("INSERT INTO frames VALUES ('legacy', 0, 0, 1, 2, 0, 3, 4, 0, 0)")

    RunStore(db_path)
    with sqlite3.connect(db_path) as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(frames)")}
        count = db.execute("SELECT COUNT(*) FROM frames").fetchone()[0]

    assert "energy_j" in columns
    assert "shoulder_angle_rad" in columns
    assert count == 1


def test_external_python_policy_contract_loads() -> None:
    scenario = load_scenario(Path(__file__).resolve().parents[1] / "worlds" / "warehouse_v0" / "scenario.json", 1)
    policy = load_policy("python:examples.policies.hold_position:HoldPositionPolicy")
    policy.reset(EpisodeContext(scenario=scenario))
    observation = PolicyObservation(step=0, sim_time=0, robot_x=1, robot_y=2, heading=0,
                                    linear_speed_m_s=0, angular_speed_rad_s=0, package_x=3, package_y=4,
                                    goal_x=5, goal_y=6, carrying=False, grasp_qualified=False, contact_force_n=0)
    action = policy.act(observation)
    assert action.target_x == 1
    assert action.target_y == 2


def test_active_run_cancellation_writes_partial_verified_evidence(tmp_path: Path) -> None:
    from worldsim.mujoco_engine import MujocoEngine

    settings = settings_for(tmp_path)
    store = RunStore(settings.db_path)
    store.create_run(RunCreate(policy_id="baseline_safe", engine_id="mujoco_v1", seed=8))
    claimed = store.claim_next()
    assert claimed
    cancelled = store.request_cancel(claimed.id)
    assert cancelled and cancelled.status == "cancelling"

    evidence = MujocoEngine(settings.scenario_path).execute(store, claimed, tmp_path, frame_delay=0)
    final = store.get_run(claimed.id)

    assert evidence["verdict"] == "cancelled"
    assert final and final.status == "cancelled"
    assert len(store.get_detail(claimed.id).frames) == 1
    assert verify_evidence_bundle(tmp_path / "runs" / claimed.id)[0] is True


def test_queued_run_can_be_cancelled_without_worker(tmp_path: Path) -> None:
    store = RunStore(settings_for(tmp_path).db_path)
    run = store.create_run(RunCreate())
    cancelled = store.request_cancel(run.id)

    assert cancelled and cancelled.status == "cancelled"
    assert store.claim_next() is None


def test_policy_subprocess_protocol_and_deadline() -> None:
    scenario = load_scenario(Path(__file__).resolve().parents[1] / "worlds" / "warehouse_v0" / "scenario.json", 2)
    context = EpisodeContext(scenario=scenario)
    observation = PolicyObservation(step=0, sim_time=0, robot_x=10, robot_y=78, heading=0,
                                    linear_speed_m_s=0, angular_speed_rad_s=0, package_x=68, package_y=32,
                                    goal_x=86, goal_y=20, carrying=False, grasp_qualified=False, contact_force_n=0)
    with IsolatedPolicyClient("baseline_safe", context, timeout_ms=100) as client:
        action = client.act(observation)
        assert action.schema_version == "1.0"
        assert action.target_x == 10

    started = time.perf_counter()
    with IsolatedPolicyClient("python:examples.policies.slow_policy:SlowPolicy", context, timeout_ms=50) as client:
        with pytest.raises(PolicyRuntimeError, match="exceeded 50 ms"):
            client.act(observation)
    assert time.perf_counter() - started < 2


def test_durable_batch_deduplicates_seeds_and_aggregates(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    store = RunStore(settings.db_path)
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/batches", json={"scenario_id": "warehouse_v0", "policy_id": "baseline_safe",
                                                      "engine_id": "deterministic_mock_v1", "seeds": [3, 4, 4]})
        assert response.status_code == 202
        batch_id = response.json()["id"]
        assert len(response.json()["runs"]) == 2

    while claimed := store.claim_next():
        execute_mock_run(store, claimed, tmp_path, frame_delay=0, scenario_path=settings.scenario_path)

    with TestClient(create_app(settings)) as client:
        batch = client.get(f"/api/batches/{batch_id}").json()
    assert batch["counts"] == {"succeeded": 2}
    assert batch["pass_rate"] == 1


def test_policy_deadline_failure_produces_partial_evidence(tmp_path: Path) -> None:
    from worldsim.mujoco_engine import MujocoEngine

    settings = settings_for(tmp_path)
    store = RunStore(settings.db_path)
    store.create_run(RunCreate(policy_id="python:examples.policies.slow_policy:SlowPolicy",
                               engine_id="mujoco_v1", seed=10))
    claimed = store.claim_next()
    assert claimed

    evidence = MujocoEngine(settings.scenario_path).execute(store, claimed, tmp_path, frame_delay=0)
    failed = store.get_run(claimed.id)

    assert evidence["verdict"] == "error"
    assert failed and failed.status == "failed"
    assert "exceeded 100 ms deadline" in failed.error
    assert evidence["metrics"]["policy_isolated"] is True
    assert verify_evidence_bundle(tmp_path / "runs" / claimed.id)[0] is True


def test_paired_experiment_gates_and_exports(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    store = RunStore(settings.db_path)
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/experiments", json={
            "scenario_id": "warehouse_v0", "candidate_policy_id": "baseline_risky",
            "baseline_policy_id": "baseline_safe", "engine_id": "deterministic_mock_v1", "seeds": [1, 2],
        })
        assert response.status_code == 202
        experiment_id = response.json()["id"]

    while claimed := store.claim_next():
        execute_mock_run(store, claimed, tmp_path, frame_delay=0, scenario_path=settings.scenario_path)

    with TestClient(create_app(settings)) as client:
        experiment = client.get(f"/api/experiments/{experiment_id}").json()
        csv_export = client.get(f"/api/experiments/{experiment_id}/export?format=csv")
        junit_export = client.get(f"/api/experiments/{experiment_id}/export?format=junit")

    assert experiment["status"] == "complete"
    assert experiment["verdict"] == "fail"
    assert experiment["summary"]["candidate_pass_rate"] == 0
    assert experiment["summary"]["baseline_pass_rate"] == 1
    assert all("max_collisions" in pair["failure_reasons"] for pair in experiment["pairs"])
    assert "candidate_verdict" in csv_export.text
    assert "<testsuite" in junit_export.text
    assert "experiment_gate" in junit_export.text


def test_batch_cancellation_and_seed_parser(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    with TestClient(create_app(settings)) as client:
        batch = client.post("/api/batches", json={"scenario_id": "warehouse_v0", "policy_id": "baseline_safe",
                                                   "engine_id": "deterministic_mock_v1", "seeds": [1, 2, 3]}).json()
        cancelled = client.post(f"/api/batches/{batch['id']}/cancel").json()

    assert cancelled["counts"] == {"cancelled": 3}
    assert parse_seeds("1..3, 3, 7") == [1, 2, 3, 7]
    with pytest.raises(ValueError):
        parse_seeds("5..2")
