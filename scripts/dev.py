from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    web_modules = ROOT / "apps" / "web" / "node_modules"
    if not web_modules.exists():
        print("Web dependencies are missing. Run `npm run setup` once, then retry.")
        return 1

    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"
    commands = [
        ("api", [sys.executable, "-m", "uvicorn", "worldsim.api:app", "--host", "127.0.0.1", "--port", "8010"]),
        ("worker", [sys.executable, "-m", "worldsim.worker"]),
        ("web", ["npm.cmd" if os.name == "nt" else "npm", "--prefix", "apps/web", "run", "dev"]),
    ]
    processes: list[tuple[str, subprocess.Popen]] = []
    try:
        for name, command in commands:
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            process = subprocess.Popen(command, cwd=ROOT, env=environment, creationflags=creation_flags)
            processes.append((name, process))
            print(f"Started {name} (pid {process.pid})")
        print("\nWorldSim Lab: http://127.0.0.1:5173")
        print("API docs:     http://127.0.0.1:8010/docs\n")
        while True:
            for name, process in processes:
                exit_code = process.poll()
                if exit_code is not None:
                    print(f"{name} stopped unexpectedly with exit code {exit_code}.")
                    return exit_code or 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping WorldSim...")
        return 0
    finally:
        for _, process in processes:
            if process.poll() is None:
                if os.name == "nt":
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    process.terminate()
        for _, process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
