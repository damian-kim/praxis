from __future__ import annotations

import importlib
import inspect
import math
from dataclasses import dataclass
from typing import Protocol

from .contracts import PolicyAction, PolicyObservation
from .simulator import interpolate


@dataclass(frozen=True)
class EpisodeContext:
    scenario: dict
    control_hz: int = 10


class WorldPolicy(Protocol):
    def reset(self, context: EpisodeContext) -> None: ...
    def act(self, observation: PolicyObservation) -> PolicyAction | dict: ...


class ReferenceWarehousePolicy:
    def __init__(self, risky: bool = False):
        self.risky = risky

    def reset(self, context: EpisodeContext) -> None:
        scenario = context.scenario
        spawn = tuple(scenario["agent"]["spawn"])
        package = tuple(scenario["task"]["package_spawn"])
        obstruction = tuple(scenario["task"]["obstruction"]["position"])
        self.goal = tuple(scenario["task"]["delivery_zone"])
        approach = (68.0, 40.0)
        heading = math.atan2(package[1] - approach[1], package[0] - approach[0])
        self.pregrasp = (package[0] - math.cos(heading) * 1.08, package[1] - math.sin(heading) * 1.08)
        self.grasp_heading = heading
        if self.risky:
            points = [spawn, (10, 52), (32, 52), obstruction, self.pregrasp]
        else:
            points = [spawn, (10, 52), (32, 52), (36, 60), (58, 60), approach, self.pregrasp]
        self.navigation = list(interpolate(points, steps_per_leg=24))
        self.navigation_index = 0
        self.grasp_steps = 0
        self.delivery = []
        self.delivery_index = 0
        self.hold_steps = 0

    def act(self, observation: PolicyObservation) -> PolicyAction:
        if self.navigation_index < len(self.navigation):
            _, x, y = self.navigation[self.navigation_index]
            next_index = min(self.navigation_index + 1, len(self.navigation) - 1)
            _, nx, ny = self.navigation[next_index]
            self.navigation_index += 1
            return PolicyAction(target_x=x, target_y=y, target_heading=math.atan2(ny - y, nx - x),
                                shoulder_target_rad=-1.02, elbow_target_rad=1.30, gripper_target_m=.12)

        if not observation.grasp_qualified:
            self.grasp_steps += 1
            closure = max(0.0, .12 * (1 - self.grasp_steps / 28))
            return PolicyAction(target_x=self.pregrasp[0], target_y=self.pregrasp[1], target_heading=self.grasp_heading,
                                shoulder_target_rad=.50, elbow_target_rad=.50, gripper_target_m=closure,
                                request_grasp=True, done=self.grasp_steps > 55)

        if not self.delivery:
            self.delivery = list(interpolate([self.pregrasp, self.goal], steps_per_leg=40))
        if self.delivery_index < len(self.delivery):
            _, x, y = self.delivery[self.delivery_index]
            next_index = min(self.delivery_index + 1, len(self.delivery) - 1)
            _, nx, ny = self.delivery[next_index]
            self.delivery_index += 1
            return PolicyAction(target_x=x, target_y=y, target_heading=math.atan2(ny - y, nx - x),
                                shoulder_target_rad=-1.02, elbow_target_rad=1.30, gripper_target_m=.01)

        self.hold_steps += 1
        return PolicyAction(target_x=self.goal[0], target_y=self.goal[1], target_heading=0,
                            shoulder_target_rad=-1.02, elbow_target_rad=1.30, gripper_target_m=.01,
                            done=self.hold_steps >= 20)


def load_policy(policy_id: str) -> WorldPolicy:
    if policy_id == "baseline_safe":
        return ReferenceWarehousePolicy(risky=False)
    if policy_id == "baseline_risky":
        return ReferenceWarehousePolicy(risky=True)
    if not policy_id.startswith("python:"):
        raise ValueError(f"Unknown policy '{policy_id}'. Use baseline_safe, baseline_risky, or python:module:object.")
    spec = policy_id.removeprefix("python:")
    try:
        module_name, object_name = spec.rsplit(":", 1)
    except ValueError as exc:
        raise ValueError("Python policy IDs must use python:module:object") from exc
    module = importlib.import_module(module_name)
    candidate = getattr(module, object_name)
    policy = candidate() if inspect.isclass(candidate) else candidate
    if not callable(getattr(policy, "reset", None)) or not callable(getattr(policy, "act", None)):
        raise TypeError("Python policy must provide reset(context) and act(observation)")
    return policy

