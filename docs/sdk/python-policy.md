# Python Policy SDK

Praxis Worlds policies are ordinary Python objects with two methods:

```python
from worldsim.contracts import PolicyAction, PolicyObservation
from worldsim.policy import EpisodeContext


class MyPolicy:
    def reset(self, context: EpisodeContext) -> None:
        self.steps = 0

    def act(self, observation: PolicyObservation) -> PolicyAction:
        self.steps += 1
        return PolicyAction(
            target_x=observation.robot_x,
            target_y=observation.robot_y,
            target_heading=observation.heading,
            shoulder_target_rad=-1.02,
            elbow_target_rad=1.30,
            gripper_target_m=.12,
            request_grasp=False,
            done=self.steps >= 20,
        )
```

Place the module somewhere importable by the worker, then enter this policy ID in Praxis Lab:

```text
python:your_package.your_module:MyPolicy
```

The included example is:

```text
python:examples.policies.hold_position:HoldPositionPolicy
```

Every observation and validated action is persisted in SQLite and written to `policy_trace.json`. Policy code is trusted local code in this release; do not load untrusted modules.

