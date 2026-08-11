from __future__ import annotations

import json
import random
from copy import deepcopy
from pathlib import Path


class ScenarioError(ValueError):
    pass


def load_scenario(path: Path, seed: int) -> dict:
    try:
        definition = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScenarioError(f"Could not load scenario: {exc}") from exc
    if definition.get("schema_version") != "1.1":
        raise ScenarioError("Unsupported scenario schema; expected 1.1")

    episode = deepcopy(definition)
    rng = random.Random(seed)
    variation = episode["variation"]
    package = episode["task"]["package_spawn"]
    obstruction = episode["task"]["obstruction"]
    package[0] += round(rng.uniform(-variation["package_jitter_m"], variation["package_jitter_m"]), 2)
    package[1] += round(rng.uniform(-variation["package_jitter_m"], variation["package_jitter_m"]), 2)
    obstruction["position"][0] += round(rng.uniform(-variation["obstruction_jitter_m"], variation["obstruction_jitter_m"]), 2)
    obstruction["rotation_deg"] += round(rng.uniform(-variation["obstruction_rotation_deg"], variation["obstruction_rotation_deg"]), 1)
    episode["episode_seed"] = seed
    return episode


def threshold_values(scenario: dict) -> dict[str, float | bool]:
    return {name: definition["value"] for name, definition in scenario["limits"].items()}

