from __future__ import annotations

import os
import time

from .config import Settings
from .engines import MOCK_CAPABILITIES, resolve_engine
from .store import RunStore


def work_once(store: RunStore, settings: Settings, frame_delay: float = 0.10) -> bool:
    store.heartbeat()
    run = store.claim_next()
    if not run:
        return False
    try:
        engine_id = os.getenv("WORLDSIM_ENGINE", run.engine_id)
        engine = resolve_engine(engine_id, settings.scenario_path)
        engine.execute(store, run, settings.data_dir, frame_delay)
    except Exception as exc:
        store.update_run(run.id, status="failed", progress=1, phase="Worker error", verdict="error", error=str(exc))
    return True


def main() -> None:
    settings = Settings.from_env()
    store = RunStore(settings.db_path)
    poll_interval = float(os.getenv("WORLDSIM_POLL_INTERVAL", "0.5"))
    frame_delay = float(os.getenv("WORLDSIM_FRAME_DELAY", "0.1"))
    print(f"WorldSim worker ready: {settings.db_path}", flush=True)
    while True:
        if not work_once(store, settings, frame_delay=frame_delay):
            time.sleep(poll_interval)


if __name__ == "__main__":
    main()
