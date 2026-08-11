from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from worldsim.api import create_app
from worldsim.config import Settings
from worldsim.contracts import RunCreate
from worldsim.simulator import execute_mock_run
from worldsim.scenario import load_scenario
from worldsim.evidence import verify_evidence_bundle
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
    assert valid is True and checked == 2 and errors == []


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
