from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    db_path: Path
    scenario_path: Path
    worlds_dir: Path | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("WORLDSIM_DATA_DIR", REPO_ROOT / ".worldsim")).resolve()
        worlds_dir = Path(os.getenv("WORLDSIM_WORLDS_DIR", REPO_ROOT / "worlds")).resolve()
        return cls(
            data_dir=data_dir,
            db_path=data_dir / "worldsim.db",
            scenario_path=worlds_dir / "warehouse_v0" / "scenario.json",
            worlds_dir=worlds_dir,
        )

    def scenario_path_for(self, scenario_id: str) -> Path:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", scenario_id):
            raise ValueError("Invalid scenario ID")
        if self.scenario_path.parent.name == scenario_id:
            return self.scenario_path
        root = self.worlds_dir or self.scenario_path.parent.parent
        return root / scenario_id / "scenario.json"
