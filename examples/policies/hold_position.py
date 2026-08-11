from worldsim.contracts import PolicyAction, PolicyObservation
from worldsim.policy import EpisodeContext


class HoldPositionPolicy:
    """Smallest valid external policy: observe once, hold, then finish."""

    def reset(self, context: EpisodeContext) -> None:
        self.steps = 0

    def act(self, observation: PolicyObservation) -> PolicyAction:
        self.steps += 1
        return PolicyAction(
            target_x=observation.robot_x,
            target_y=observation.robot_y,
            target_heading=observation.heading,
            done=self.steps >= 20,
        )
