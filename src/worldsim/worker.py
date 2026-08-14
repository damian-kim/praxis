from __future__ import annotations

import os
import socket
import threading
import time
import uuid

from .config import Settings
from .engines import MOCK_CAPABILITIES, resolve_engine
from .store import RunStore


def work_once(store: RunStore, settings: Settings, frame_delay: float = 0.10,
              worker_id: str | None = None, max_active: int = 1) -> bool:
    store.heartbeat(worker_id)
    run = store.claim_next(worker_id, max_active=max_active)
    if not run:
        return False
    stop_heartbeat = threading.Event()
    heartbeat_thread = None
    if worker_id:
        def maintain_lease() -> None:
            while not stop_heartbeat.wait(2):
                store.heartbeat(worker_id)
        heartbeat_thread = threading.Thread(target=maintain_lease, name="praxis-worker-heartbeat", daemon=True)
        heartbeat_thread.start()
    try:
        engine_id = run.engine_id
        scenario_path = settings.scenario_path_for(run.scenario_id)
        if not scenario_path.is_file():
            raise RuntimeError(f"Scenario '{run.scenario_id}' is not installed")
        engine = resolve_engine(engine_id, scenario_path)
        engine.execute(store, run, settings.data_dir, frame_delay)
    except Exception as exc:
        store.update_run(run.id, status="failed", progress=1, phase="Worker error", verdict="error", error=str(exc))
    finally:
        stop_heartbeat.set()
        if heartbeat_thread:
            heartbeat_thread.join(timeout=3)
        if worker_id:
            store.release_worker_run(worker_id)
    return True


def main() -> None:
    settings = Settings.from_env()
    store = RunStore(settings.db_path)
    poll_interval = float(os.getenv("WORLDSIM_POLL_INTERVAL", "0.5"))
    frame_delay = float(os.getenv("WORLDSIM_FRAME_DELAY", "0.1"))
    max_active = max(1, int(os.getenv("WORLDSIM_MAX_ACTIVE_RUNS", "1")))
    worker_id = f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    store.register_worker(worker_id, max_active_runs=max_active)
    print(f"Praxis worker {worker_id} ready: {settings.db_path} (global concurrency {max_active})", flush=True)
    try:
        while True:
            if not work_once(store, settings, frame_delay=frame_delay, worker_id=worker_id, max_active=max_active):
                time.sleep(poll_interval)
    finally:
        store.unregister_worker(worker_id)


if __name__ == "__main__":
    main()
