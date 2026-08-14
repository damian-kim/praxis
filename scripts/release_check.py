from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from worldsim.api import create_app
from worldsim.config import REPO_ROOT, Settings
from worldsim.simulator import execute_mock_run
from worldsim.store import RunStore


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="praxis-release-") as temporary:
        data_dir = Path(temporary)
        worlds_dir = REPO_ROOT / "worlds"
        settings = Settings(data_dir, data_dir / "worldsim.db",
                            worlds_dir / "warehouse_v0" / "scenario.json", worlds_dir)
        store = RunStore(settings.db_path)
        with TestClient(create_app(settings)) as client:
            scenarios = client.get("/api/scenarios")
            assert scenarios.status_code == 200 and len(scenarios.json()) >= 2
            response = client.post("/api/suite-evaluations", json={
                "suite_id": "warehouse_smoke", "candidate_policy_id": "baseline_safe",
                "baseline_policy_id": "baseline_safe", "engine_id": "deterministic_mock_v1",
            })
            assert response.status_code == 202, response.text
            evaluation_id = response.json()["id"]
        while run := store.claim_next():
            execute_mock_run(store, run, data_dir, frame_delay=0,
                             scenario_path=settings.scenario_path_for(run.scenario_id))
        with TestClient(create_app(settings)) as restarted:
            evaluation = restarted.get(f"/api/suite-evaluations/{evaluation_id}")
            assert evaluation.status_code == 200
            payload = evaluation.json()
            assert payload["status"] == "complete" and payload["verdict"] == "pass"
            for experiment in payload["scenario_results"]:
                for pair in experiment["pairs"]:
                    for side in ("candidate_run", "baseline_run"):
                        verification = restarted.get(f"/api/runs/{pair[side]['id']}/evidence/verify")
                        assert verification.json()["valid"] is True
        print(f"release smoke passed: {payload['total_pairs']} pairs across {len(payload['scenario_results'])} worlds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
