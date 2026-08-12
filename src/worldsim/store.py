from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterator

from .contracts import Batch, BatchCreate, Experiment, ExperimentCreate, Frame, GateConfig, Run, RunCreate, RunDetail, SeedComparison, WorkerState
from .statistics import experiment_confidence


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class RunStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    policy_id TEXT NOT NULL,
                    engine_id TEXT NOT NULL DEFAULT 'deterministic_mock_v1',
                    seed INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0,
                    phase TEXT NOT NULL,
                    verdict TEXT,
                    error TEXT,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    metrics_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                    sequence INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    message TEXT NOT NULL,
                    sim_time REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (run_id, sequence)
                );
                CREATE TABLE IF NOT EXISTS frames (
                    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                    sequence INTEGER NOT NULL,
                    sim_time REAL NOT NULL,
                    robot_x REAL NOT NULL,
                    robot_y REAL NOT NULL,
                    heading REAL NOT NULL,
                    package_x REAL NOT NULL,
                    package_y REAL NOT NULL,
                    carrying INTEGER NOT NULL,
                    contact_force REAL NOT NULL,
                    linear_speed_m_s REAL,
                    angular_speed_rad_s REAL,
                    shoulder_angle_rad REAL,
                    elbow_angle_rad REAL,
                    gripper_width_m REAL,
                    energy_j REAL,
                    PRIMARY KEY (run_id, sequence)
                );
                CREATE TABLE IF NOT EXISTS system_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS policy_steps (
                    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                    sequence INTEGER NOT NULL,
                    observation_json TEXT NOT NULL,
                    action_json TEXT NOT NULL,
                    decision_ms REAL NOT NULL,
                    PRIMARY KEY (run_id, sequence)
                );
                CREATE TABLE IF NOT EXISTS batches (
                    id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    policy_id TEXT NOT NULL,
                    engine_id TEXT NOT NULL,
                    seeds_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS batch_runs (
                    batch_id TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
                    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                    seed INTEGER NOT NULL,
                    PRIMARY KEY (batch_id, run_id)
                );
                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    candidate_policy_id TEXT NOT NULL,
                    baseline_policy_id TEXT NOT NULL,
                    engine_id TEXT NOT NULL,
                    seeds_json TEXT NOT NULL,
                    candidate_batch_id TEXT NOT NULL REFERENCES batches(id),
                    baseline_batch_id TEXT NOT NULL REFERENCES batches(id),
                    gates_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workers (
                    id TEXT PRIMARY KEY,
                    process_id INTEGER NOT NULL,
                    max_active_runs INTEGER NOT NULL DEFAULT 1,
                    started_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    current_run_id TEXT
                );
            """)
            columns = {row["name"] for row in db.execute("PRAGMA table_info(runs)")}
            if "engine_id" not in columns:
                db.execute("ALTER TABLE runs ADD COLUMN engine_id TEXT NOT NULL DEFAULT 'deterministic_mock_v1'")
            if "cancel_requested" not in columns:
                db.execute("ALTER TABLE runs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0")
            frame_columns = {row["name"] for row in db.execute("PRAGMA table_info(frames)")}
            telemetry_columns = {
                "linear_speed_m_s": "REAL", "angular_speed_rad_s": "REAL",
                "shoulder_angle_rad": "REAL", "elbow_angle_rad": "REAL",
                "gripper_width_m": "REAL", "energy_j": "REAL",
            }
            for name, sql_type in telemetry_columns.items():
                if name not in frame_columns:
                    db.execute(f"ALTER TABLE frames ADD COLUMN {name} {sql_type}")
            worker_columns = {row["name"] for row in db.execute("PRAGMA table_info(workers)")}
            if "max_active_runs" not in worker_columns:
                db.execute("ALTER TABLE workers ADD COLUMN max_active_runs INTEGER NOT NULL DEFAULT 1")

    def create_run(self, request: RunCreate) -> Run:
        timestamp = now_iso()
        run_id = f"run_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
        with self.connect() as db:
            db.execute(
                "INSERT INTO runs (id, scenario_id, policy_id, engine_id, seed, status, progress, phase, verdict, error, cancel_requested, metrics_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'queued', 0, 'Waiting for worker', NULL, NULL, 0, '{}', ?, ?)",
                (run_id, request.scenario_id, request.policy_id, request.engine_id, request.seed, timestamp, timestamp),
            )
            db.execute(
                "INSERT INTO events VALUES (?, 0, 'lifecycle', 'Run queued', 0, ?)",
                (run_id, timestamp),
            )
        return self.get_run(run_id)

    def list_runs(self, limit: int = 50) -> list[Run]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._run(row) for row in rows]

    def create_batch(self, request: BatchCreate) -> Batch:
        unique_seeds = list(dict.fromkeys(request.seeds))
        batch_id = f"batch_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
        timestamp = now_iso()
        with self.connect() as db:
            db.execute("INSERT INTO batches VALUES (?, ?, ?, ?, ?, ?)",
                       (batch_id, request.scenario_id, request.policy_id, request.engine_id,
                        json.dumps(unique_seeds), timestamp))
        for seed in unique_seeds:
            run = self.create_run(RunCreate(scenario_id=request.scenario_id, policy_id=request.policy_id,
                                            engine_id=request.engine_id, seed=seed))
            with self.connect() as db:
                db.execute("INSERT INTO batch_runs VALUES (?, ?, ?)", (batch_id, run.id, seed))
        return self.get_batch(batch_id)

    def get_batch(self, batch_id: str) -> Batch | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
            if not row:
                return None
            run_rows = db.execute("SELECT runs.* FROM runs JOIN batch_runs ON runs.id=batch_runs.run_id WHERE batch_runs.batch_id=? ORDER BY batch_runs.seed", (batch_id,)).fetchall()
        runs = [self._run(run_row) for run_row in run_rows]
        counts: dict[str, int] = {}
        for run in runs:
            counts[run.status] = counts.get(run.status, 0) + 1
        finished = [run for run in runs if run.status in {"succeeded", "failed", "cancelled", "interrupted"}]
        passes = sum(run.verdict == "pass" for run in finished)
        return Batch(id=row["id"], scenario_id=row["scenario_id"], policy_id=row["policy_id"],
                     engine_id=row["engine_id"], seeds=json.loads(row["seeds_json"]), created_at=row["created_at"],
                     counts=counts, pass_rate=(passes / len(finished) if finished else None), runs=runs)

    def list_batches(self, limit: int = 20) -> list[Batch]:
        with self.connect() as db:
            ids = [row["id"] for row in db.execute("SELECT id FROM batches ORDER BY created_at DESC LIMIT ?", (limit,))]
        return [batch for batch_id in ids if (batch := self.get_batch(batch_id)) is not None]

    def cancel_batch(self, batch_id: str) -> Batch | None:
        batch = self.get_batch(batch_id)
        if not batch:
            return None
        for run in batch.runs:
            self.request_cancel(run.id)
        return self.get_batch(batch_id)

    def create_experiment(self, request: ExperimentCreate) -> Experiment:
        unique_seeds = list(dict.fromkeys(request.seeds))
        baseline = self.create_batch(BatchCreate(scenario_id=request.scenario_id, policy_id=request.baseline_policy_id,
                                                  engine_id=request.engine_id, seeds=unique_seeds))
        candidate = self.create_batch(BatchCreate(scenario_id=request.scenario_id, policy_id=request.candidate_policy_id,
                                                   engine_id=request.engine_id, seeds=unique_seeds))
        experiment_id = f"exp_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
        timestamp = now_iso()
        with self.connect() as db:
            db.execute("INSERT INTO experiments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (experiment_id, request.scenario_id, request.candidate_policy_id, request.baseline_policy_id,
                        request.engine_id, json.dumps(unique_seeds), candidate.id, baseline.id,
                        request.gates.model_dump_json(), timestamp))
        return self.get_experiment(experiment_id)

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM experiments WHERE id=?", (experiment_id,)).fetchone()
        if not row:
            return None
        candidate = self.get_batch(row["candidate_batch_id"])
        baseline = self.get_batch(row["baseline_batch_id"])
        if not candidate or not baseline:
            return None
        seeds = json.loads(row["seeds_json"])
        gates = GateConfig.model_validate_json(row["gates_json"])
        candidate_by_seed = {run.seed: run for run in candidate.runs}
        baseline_by_seed = {run.seed: run for run in baseline.runs}
        metric_keys = ["collisions", "max_contact_force_n", "sim_duration_s", "actuator_energy_j"]
        pairs = []
        for seed in seeds:
            candidate_run, baseline_run = candidate_by_seed[seed], baseline_by_seed[seed]
            deltas = {}
            for key in metric_keys:
                first, second = candidate_run.metrics.get(key), baseline_run.metrics.get(key)
                deltas[key] = float(first - second) if self._is_number(first) and self._is_number(second) else None
            reasons = []
            if candidate_run.status in {"failed", "cancelled", "interrupted"}:
                checks = candidate_run.metrics.get("checks", [])
                reasons = [check["id"] for check in checks if not check.get("passed", True)]
                if candidate_run.error:
                    reasons.append("policy_or_worker_error")
                if not reasons:
                    reasons.append(candidate_run.verdict or candidate_run.status)
            pairs.append(SeedComparison(seed=seed, candidate_run=candidate_run, baseline_run=baseline_run,
                                        metric_deltas=deltas, failure_reasons=reasons))
        terminal = {"succeeded", "failed", "cancelled", "interrupted"}
        complete = all(pair.candidate_run.status in terminal and pair.baseline_run.status in terminal for pair in pairs)
        candidate_passes = sum(pair.candidate_run.verdict == "pass" for pair in pairs)
        baseline_passes = sum(pair.baseline_run.verdict == "pass" for pair in pairs)
        candidate_pass_rate = candidate_passes / len(pairs) if complete else None
        baseline_pass_rate = baseline_passes / len(pairs) if complete else None

        delta_values = {key: [pair.metric_deltas[key] for pair in pairs if pair.metric_deltas[key] is not None]
                        for key in metric_keys}

        def mean_delta(key: str) -> float | None:
            values = delta_values[key]
            return sum(values) / len(values) if values and complete else None

        summary = {
            "candidate_pass_rate": candidate_pass_rate,
            "baseline_pass_rate": baseline_pass_rate,
            "pass_rate_delta": (candidate_pass_rate - baseline_pass_rate) if complete else None,
            "mean_collision_delta": mean_delta("collisions"),
            "mean_force_delta_n": mean_delta("max_contact_force_n"),
            "mean_duration_delta_s": mean_delta("sim_duration_s"),
            "mean_energy_delta_j": mean_delta("actuator_energy_j"),
            "completed_pairs": sum(pair.candidate_run.status in terminal and pair.baseline_run.status in terminal for pair in pairs),
            "total_pairs": len(pairs),
        }
        summary["confidence"] = (experiment_confidence(candidate_passes, baseline_passes, len(pairs), delta_values)
                                 if complete else None)
        gate_results = self._gate_results(gates, summary) if complete else []
        verdict = "pass" if complete and all(result["passed"] for result in gate_results) else "fail" if complete else "pending"
        return Experiment(id=row["id"], scenario_id=row["scenario_id"], candidate_policy_id=row["candidate_policy_id"],
                          baseline_policy_id=row["baseline_policy_id"], engine_id=row["engine_id"], seeds=seeds,
                          candidate_batch_id=row["candidate_batch_id"], baseline_batch_id=row["baseline_batch_id"],
                          gates=gates, created_at=row["created_at"], status="complete" if complete else "running",
                          verdict=verdict, summary=summary, gate_results=gate_results, pairs=pairs)

    def list_experiments(self, limit: int = 20) -> list[Experiment]:
        with self.connect() as db:
            ids = [row["id"] for row in db.execute("SELECT id FROM experiments ORDER BY created_at DESC LIMIT ?", (limit,))]
        return [experiment for experiment_id in ids if (experiment := self.get_experiment(experiment_id)) is not None]

    def cancel_experiment(self, experiment_id: str) -> Experiment | None:
        experiment = self.get_experiment(experiment_id)
        if not experiment:
            return None
        self.cancel_batch(experiment.candidate_batch_id)
        self.cancel_batch(experiment.baseline_batch_id)
        return self.get_experiment(experiment_id)

    @staticmethod
    def _is_number(value: object) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    @staticmethod
    def _gate_results(gates: GateConfig, summary: dict) -> list[dict]:
        definitions = [
            ("candidate_pass_rate", summary["candidate_pass_rate"], ">=", gates.min_candidate_pass_rate,
             summary["candidate_pass_rate"] >= gates.min_candidate_pass_rate),
            ("pass_rate_drop", -summary["pass_rate_delta"], "<=", gates.max_pass_rate_drop,
             -summary["pass_rate_delta"] <= gates.max_pass_rate_drop),
            ("mean_collision_increase", summary["mean_collision_delta"], "<=", gates.max_mean_collision_increase,
             summary["mean_collision_delta"] <= gates.max_mean_collision_increase),
            ("mean_force_increase_n", summary["mean_force_delta_n"], "<=", gates.max_mean_force_increase_n,
             summary["mean_force_delta_n"] <= gates.max_mean_force_increase_n),
            ("mean_duration_increase_s", summary["mean_duration_delta_s"], "<=", gates.max_mean_duration_increase_s,
             summary["mean_duration_delta_s"] <= gates.max_mean_duration_increase_s),
        ]
        return [{"id": gate_id, "actual": actual, "operator": operator, "limit": limit, "passed": passed}
                for gate_id, actual, operator, limit, passed in definitions]

    def get_run(self, run_id: str) -> Run | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return self._run(row) if row else None

    def get_detail(self, run_id: str) -> RunDetail | None:
        run = self.get_run(run_id)
        if not run:
            return None
        with self.connect() as db:
            events = [dict(row) for row in db.execute(
                "SELECT sequence, kind, message, sim_time, created_at FROM events WHERE run_id=? ORDER BY sequence", (run_id,)
            )]
            frames = [dict(row) for row in db.execute(
                "SELECT sequence, sim_time, robot_x, robot_y, heading, package_x, package_y, carrying, contact_force, linear_speed_m_s, angular_speed_rad_s, shoulder_angle_rad, elbow_angle_rad, gripper_width_m, energy_j FROM frames WHERE run_id=? ORDER BY sequence", (run_id,)
            )]
        for frame in frames:
            frame["carrying"] = bool(frame["carrying"])
        return RunDetail(**run.model_dump(), events=events, frames=frames)

    def register_worker(self, worker_id: str, process_id: int | None = None, max_active_runs: int = 1) -> WorkerState:
        timestamp = now_iso()
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO workers (id, process_id, max_active_runs, started_at, last_seen_at, current_run_id) VALUES (?, ?, ?, ?, ?, NULL)",
                       (worker_id, process_id or os.getpid(), max(1, max_active_runs), timestamp, timestamp))
        return self.get_worker(worker_id)

    def get_worker(self, worker_id: str) -> WorkerState | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM workers WHERE id=?", (worker_id,)).fetchone()
        return WorkerState(id=row["id"], process_id=row["process_id"], max_active_runs=row["max_active_runs"], started_at=row["started_at"],
                           last_seen_at=row["last_seen_at"], current_run_id=row["current_run_id"]) if row else None

    def list_workers(self, lease_seconds: float = 10) -> list[WorkerState]:
        self.recover_stale_workers(lease_seconds)
        with self.connect() as db:
            rows = db.execute("SELECT * FROM workers ORDER BY started_at").fetchall()
        return [WorkerState(id=row["id"], process_id=row["process_id"], max_active_runs=row["max_active_runs"], started_at=row["started_at"],
                            last_seen_at=row["last_seen_at"], current_run_id=row["current_run_id"]) for row in rows]

    def recover_stale_workers(self, lease_seconds: float = 10) -> int:
        cutoff = (datetime.now(UTC) - timedelta(seconds=lease_seconds)).isoformat()
        with self.connect() as db:
            stale = db.execute("SELECT current_run_id FROM workers WHERE last_seen_at < ? AND current_run_id IS NOT NULL", (cutoff,)).fetchall()
            for row in stale:
                db.execute("UPDATE runs SET status='interrupted', verdict='error', phase='Worker lease expired', error='Worker heartbeat expired during execution', updated_at=? WHERE id=? AND status IN ('provisioning','loading','running','finalizing')",
                           (now_iso(), row["current_run_id"]))
            removed = db.execute("DELETE FROM workers WHERE last_seen_at < ?", (cutoff,)).rowcount
        return removed

    def claim_next(self, worker_id: str | None = None, max_active: int = 1, lease_seconds: float = 10) -> Run | None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if worker_id:
                cutoff = (datetime.now(UTC) - timedelta(seconds=lease_seconds)).isoformat()
                stale = db.execute("SELECT current_run_id FROM workers WHERE last_seen_at < ? AND current_run_id IS NOT NULL", (cutoff,)).fetchall()
                for stale_row in stale:
                    db.execute("UPDATE runs SET status='interrupted', verdict='error', phase='Worker lease expired', error='Worker heartbeat expired during execution', updated_at=? WHERE id=? AND status IN ('provisioning','loading','running','finalizing')",
                               (now_iso(), stale_row["current_run_id"]))
                db.execute("DELETE FROM workers WHERE last_seen_at < ?", (cutoff,))
                capacity = db.execute("SELECT MIN(max_active_runs) AS capacity FROM workers").fetchone()["capacity"]
                active = db.execute("SELECT COUNT(*) AS count FROM workers WHERE current_run_id IS NOT NULL").fetchone()["count"]
                if active >= min(max(1, max_active), capacity or 1):
                    return None
            row = db.execute("SELECT id FROM runs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if not row:
                return None
            timestamp = now_iso()
            changed = db.execute(
                "UPDATE runs SET status='provisioning', phase='Worker claimed run', progress=0.02, updated_at=? WHERE id=? AND status='queued'",
                (timestamp, row["id"]),
            ).rowcount
            if not changed:
                return None
            claimed = db.execute("SELECT * FROM runs WHERE id=?", (row["id"],)).fetchone()
            if worker_id:
                db.execute("UPDATE workers SET current_run_id=?, last_seen_at=? WHERE id=?",
                           (row["id"], timestamp, worker_id))
        return self._run(claimed)

    def release_worker_run(self, worker_id: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE workers SET current_run_id=NULL, last_seen_at=? WHERE id=?", (now_iso(), worker_id))

    def unregister_worker(self, worker_id: str) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM workers WHERE id=?", (worker_id,))

    def queue_status(self) -> dict[str, int]:
        with self.connect() as db:
            queued = db.execute("SELECT COUNT(*) AS count FROM runs WHERE status='queued'").fetchone()["count"]
            active = db.execute("SELECT COUNT(*) AS count FROM workers WHERE current_run_id IS NOT NULL").fetchone()["count"]
            workers = db.execute("SELECT COUNT(*) AS count FROM workers").fetchone()["count"]
        return {"queued_runs": queued, "active_runs": active, "active_workers": workers}

    def update_run(self, run_id: str, *, status: str, progress: float, phase: str,
                   verdict: str | None = None, error: str | None = None, metrics: dict | None = None) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE runs SET status=?, progress=?, phase=?, verdict=COALESCE(?, verdict), error=?, metrics_json=COALESCE(?, metrics_json), updated_at=? WHERE id=?",
                (status, progress, phase, verdict, error, json.dumps(metrics) if metrics is not None else None, now_iso(), run_id),
            )

    def add_event(self, run_id: str, sequence: int, kind: str, message: str, sim_time: float) -> None:
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO events VALUES (?, ?, ?, ?, ?, ?)",
                       (run_id, sequence, kind, message, sim_time, now_iso()))

    def add_frame(self, run_id: str, frame: Frame) -> None:
        with self.connect() as db:
            db.execute("""INSERT OR REPLACE INTO frames
                (run_id, sequence, sim_time, robot_x, robot_y, heading, package_x, package_y, carrying, contact_force,
                 linear_speed_m_s, angular_speed_rad_s, shoulder_angle_rad, elbow_angle_rad, gripper_width_m, energy_j)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
                run_id, frame.sequence, frame.sim_time, frame.robot_x, frame.robot_y, frame.heading,
                frame.package_x, frame.package_y, int(frame.carrying), frame.contact_force,
                frame.linear_speed_m_s, frame.angular_speed_rad_s, frame.shoulder_angle_rad,
                frame.elbow_angle_rad, frame.gripper_width_m, frame.energy_j,
            ))

    def add_policy_step(self, run_id: str, sequence: int, observation: dict, action: dict, decision_ms: float) -> None:
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO policy_steps VALUES (?, ?, ?, ?, ?)",
                       (run_id, sequence, json.dumps(observation), json.dumps(action), decision_ms))

    def get_policy_steps(self, run_id: str) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT sequence, observation_json, action_json, decision_ms FROM policy_steps WHERE run_id=? ORDER BY sequence", (run_id,)).fetchall()
        return [{"sequence": row["sequence"], "observation": json.loads(row["observation_json"]),
                 "action": json.loads(row["action_json"]), "decision_ms": row["decision_ms"]} for row in rows]

    def request_cancel(self, run_id: str) -> Run | None:
        run = self.get_run(run_id)
        if not run:
            return None
        if run.status == "queued":
            self.update_run(run_id, status="cancelled", progress=run.progress, phase="Cancelled before execution", verdict="cancelled")
        elif run.status in {"provisioning", "loading", "running", "finalizing"}:
            with self.connect() as db:
                db.execute("UPDATE runs SET cancel_requested=1, status='cancelling', phase='Cancellation requested', updated_at=? WHERE id=?", (now_iso(), run_id))
        return self.get_run(run_id)

    def is_cancel_requested(self, run_id: str) -> bool:
        with self.connect() as db:
            row = db.execute("SELECT cancel_requested FROM runs WHERE id=?", (run_id,)).fetchone()
        return bool(row and row["cancel_requested"])

    def append_event(self, run_id: str, kind: str, message: str, sim_time: float) -> None:
        with self.connect() as db:
            row = db.execute("SELECT COALESCE(MAX(sequence), -1) + 1 AS sequence FROM events WHERE run_id=?", (run_id,)).fetchone()
            db.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
                       (run_id, row["sequence"], kind, message, sim_time, now_iso()))

    def heartbeat(self, worker_id: str | None = None) -> None:
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO system_state VALUES ('worker_seen_at', ?)", (now_iso(),))
            if worker_id:
                db.execute("UPDATE workers SET last_seen_at=? WHERE id=?", (now_iso(), worker_id))

    def worker_seen_at(self) -> str | None:
        with self.connect() as db:
            row = db.execute("SELECT value FROM system_state WHERE key='worker_seen_at'").fetchone()
        return row["value"] if row else None

    @staticmethod
    def _run(row: sqlite3.Row) -> Run:
        data = dict(row)
        data["metrics"] = json.loads(data.pop("metrics_json"))
        data["cancel_requested"] = bool(data["cancel_requested"])
        return Run(**data)
