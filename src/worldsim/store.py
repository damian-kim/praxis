from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from .contracts import Frame, Run, RunCreate, RunDetail


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
            """)
            columns = {row["name"] for row in db.execute("PRAGMA table_info(runs)")}
            if "engine_id" not in columns:
                db.execute("ALTER TABLE runs ADD COLUMN engine_id TEXT NOT NULL DEFAULT 'deterministic_mock_v1'")
            frame_columns = {row["name"] for row in db.execute("PRAGMA table_info(frames)")}
            telemetry_columns = {
                "linear_speed_m_s": "REAL", "angular_speed_rad_s": "REAL",
                "shoulder_angle_rad": "REAL", "elbow_angle_rad": "REAL",
                "gripper_width_m": "REAL", "energy_j": "REAL",
            }
            for name, sql_type in telemetry_columns.items():
                if name not in frame_columns:
                    db.execute(f"ALTER TABLE frames ADD COLUMN {name} {sql_type}")

    def create_run(self, request: RunCreate) -> Run:
        timestamp = now_iso()
        run_id = f"run_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
        with self.connect() as db:
            db.execute(
                "INSERT INTO runs (id, scenario_id, policy_id, engine_id, seed, status, progress, phase, verdict, error, metrics_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'queued', 0, 'Waiting for worker', NULL, NULL, '{}', ?, ?)",
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

    def claim_next(self) -> Run | None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
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
        return self._run(claimed)

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

    def heartbeat(self) -> None:
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO system_state VALUES ('worker_seen_at', ?)", (now_iso(),))

    def worker_seen_at(self) -> str | None:
        with self.connect() as db:
            row = db.execute("SELECT value FROM system_state WHERE key='worker_seen_at'").fetchone()
        return row["value"] if row else None

    @staticmethod
    def _run(row: sqlite3.Row) -> Run:
        data = dict(row)
        data["metrics"] = json.loads(data.pop("metrics_json"))
        return Run(**data)
