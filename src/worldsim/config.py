from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    db_path: Path
    scenario_path: Path

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("WORLDSIM_DATA_DIR", REPO_ROOT / ".worldsim")).resolve()
        return cls(
            data_dir=data_dir,
            db_path=data_dir / "worldsim.db",
            scenario_path=REPO_ROOT / "worlds" / "warehouse_v0" / "scenario.json",
        )

