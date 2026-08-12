from __future__ import annotations

from .contracts import EvaluationSuite


EVALUATION_SUITES = [
    EvaluationSuite(id="warehouse_smoke", name="Warehouse smoke", scenario_id="warehouse_v0",
                    seeds=[1, 2, 3], purpose="Fast local policy and integration check",
                    description="Three stable seeds for rapid development feedback."),
    EvaluationSuite(id="warehouse_regression", name="Warehouse regression", scenario_id="warehouse_v0",
                    seeds=list(range(1, 11)), purpose="Default pull-request regression screen",
                    description="Ten paired layouts; meets Praxis minimum sample guidance."),
    EvaluationSuite(id="warehouse_extended", name="Warehouse extended", scenario_id="warehouse_v0",
                    seeds=list(range(1, 26)), purpose="Pre-release robustness screen",
                    description="Twenty-five paired layouts with a narrower pass-rate confidence interval."),
]


def list_suites() -> list[EvaluationSuite]:
    return EVALUATION_SUITES
