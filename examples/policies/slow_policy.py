import time

from worldsim.contracts import PolicyAction, PolicyObservation
from worldsim.policy import EpisodeContext


class SlowPolicy:
    """Test fixture demonstrating hard policy decision deadlines."""

    def reset(self, context: EpisodeContext) -> None:
        pass

    def act(self, observation: PolicyObservation) -> PolicyAction:
        time.sleep(.25)
        return PolicyAction(target_x=observation.robot_x, target_y=observation.robot_y,
                            target_heading=observation.heading)
