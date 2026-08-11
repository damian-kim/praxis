from __future__ import annotations

import math
import time
from pathlib import Path

from .contracts import Frame, Run
from .engines import MOCK_CAPABILITIES
from .evaluator import evaluate
from .evidence import write_evidence_bundle
from .scenario import load_scenario
from .store import RunStore


def interpolate(points: list[tuple[float, float]], steps_per_leg: int = 12):
    for leg, (start, end) in enumerate(zip(points, points[1:])):
        for step in range(steps_per_leg):
            t = step / steps_per_leg
            yield leg, start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t
    yield len(points) - 2, *points[-1]


def execute_mock_run(store: RunStore, run: Run, evidence_root: Path, frame_delay: float = 0.10,
                     scenario_path: Path | None = None) -> dict:
    if scenario_path is None:
        scenario_path = Path(__file__).resolve().parents[2] / "worlds" / "warehouse_v0" / "scenario.json"
    scenario = load_scenario(scenario_path, run.seed)
    package_spawn = scenario["task"]["package_spawn"]
    obstruction = scenario["task"]["obstruction"]["position"]
    waypoints = [tuple(scenario["agent"]["spawn"]), (30, 62), tuple(obstruction), tuple(package_spawn), tuple(scenario["task"]["delivery_zone"])]
    store.update_run(run.id, status="loading", progress=0.06, phase="Loading warehouse_v0")
    store.add_event(run.id, 1, "lifecycle", f"Warehouse loaded with seed {run.seed}", 0)
    time.sleep(frame_delay)
    store.update_run(run.id, status="running", progress=0.10, phase="Navigating to package")

    package = [float(package_spawn[0]), float(package_spawn[1])]
    event_sequence = 2
    max_force = 0.0
    collisions = 0
    frames: list[dict] = []
    cancelled = False
    trajectory = list(interpolate(waypoints))
    for sequence, (leg, x, y) in enumerate(trajectory):
        if store.is_cancel_requested(run.id):
            cancelled = True
            store.append_event(run.id, "lifecycle", "Mock worker acknowledged cancellation", sequence * .1)
            break
        next_index = min(sequence + 1, len(trajectory) - 1)
        _, nx, ny = trajectory[next_index]
        heading = math.atan2(ny - y, nx - x)
        carrying = leg >= 3
        if carrying:
            package[:] = [x + math.cos(heading) * 3, y + math.sin(heading) * 3]

        contact_force = 0.0
        if run.policy_id == "baseline_risky" and 18 <= sequence <= 21:
            contact_force = 145.0 + (run.seed % 17)
            max_force = max(max_force, contact_force)
            if sequence == 18:
                collisions += 1
                store.add_event(run.id, event_sequence, "contact", "Unsafe shelf contact detected", sequence * 0.1)
                event_sequence += 1

        if sequence == 24:
            store.add_event(run.id, event_sequence, "task", "Obstruction cleared", sequence * 0.1)
            event_sequence += 1
        if sequence == 36:
            store.add_event(run.id, event_sequence, "task", "Package grasped", sequence * 0.1)
            event_sequence += 1

        frame = Frame(sequence=sequence, sim_time=round(sequence * 0.1, 2), robot_x=x, robot_y=y,
                      heading=heading, package_x=package[0], package_y=package[1], carrying=carrying,
                      contact_force=contact_force)
        store.add_frame(run.id, frame)
        frames.append(frame.model_dump())
        store.update_run(run.id, status="running", progress=0.10 + 0.82 * ((sequence + 1) / len(trajectory)),
                         phase=["Navigating", "Clearing obstruction", "Approaching package", "Delivering package"][min(leg, 3)])
        time.sleep(frame_delay)

    if not frames:
        frame = Frame(sequence=0, sim_time=0, robot_x=waypoints[0][0], robot_y=waypoints[0][1], heading=0,
                      package_x=package[0], package_y=package[1], carrying=False, contact_force=0)
        store.add_frame(run.id, frame)
        frames.append(frame.model_dump())
    metrics = {
        "task_completed": not cancelled,
        "grasp_qualified": not cancelled,
        "collisions": collisions,
        "max_contact_force_n": max_force,
        "sim_duration_s": frames[-1]["sim_time"],
        "frames_recorded": len(frames),
        "deterministic_seed": run.seed,
    }
    verdict, checks = ("cancelled", []) if cancelled else evaluate(metrics, scenario)
    failed = verdict == "fail"
    metrics["checks"] = checks
    if not cancelled:
        store.update_run(run.id, status="finalizing", progress=0.96, phase="Writing immutable evidence")
    run_dir = evidence_root / "runs" / run.id
    run_dir.mkdir(parents=True, exist_ok=True)
    evidence = {
        "schema_version": "2.0",
        "frame_schema_version": "2.0",
        "engine": MOCK_CAPABILITIES.__dict__,
        "run_id": run.id,
        "scenario_id": run.scenario_id,
        "policy_id": run.policy_id,
        "seed": run.seed,
        "verdict": verdict,
        "metrics": metrics,
        "scenario_snapshot": scenario,
        "trajectory": frames,
    }
    write_evidence_bundle(run_dir, evidence)
    store.add_event(run.id, event_sequence, "verdict", f"Run {verdict.upper()}", frames[-1]["sim_time"])
    store.update_run(run.id, status="cancelled" if cancelled else "failed" if failed else "succeeded", progress=1.0,
                     phase="Cancelled with partial evidence" if cancelled else "Evaluation complete", verdict=verdict, metrics=metrics)
    return evidence
