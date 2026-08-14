from __future__ import annotations

from .contracts import EvaluationSuite, SuiteCase


EVALUATION_SUITES = [
    EvaluationSuite(id="warehouse_smoke", name="Warehouse smoke",
                    cases=[SuiteCase(scenario_id="warehouse_v0", seeds=[1, 2]),
                           SuiteCase(scenario_id="warehouse_low_friction_v0", seeds=[1])],
                    purpose="Fast local policy and integration check",
                    description="Three paired trials across nominal and low-friction worlds."),
    EvaluationSuite(id="warehouse_regression", name="Warehouse regression",
                    cases=[SuiteCase(scenario_id="warehouse_v0", seeds=list(range(1, 6))),
                           SuiteCase(scenario_id="warehouse_low_friction_v0", seeds=list(range(1, 6)))],
                    purpose="Default pull-request regression screen",
                    description="Ten paired trials across two physical conditions."),
    EvaluationSuite(id="warehouse_extended", name="Warehouse extended",
                    cases=[SuiteCase(scenario_id="warehouse_v0", seeds=list(range(1, 14))),
                           SuiteCase(scenario_id="warehouse_low_friction_v0", seeds=list(range(1, 13)))],
                    purpose="Pre-release robustness screen",
                    description="Twenty-five paired trials with scenario-level results."),
]


def list_suites() -> list[EvaluationSuite]:
    return EVALUATION_SUITES


def get_suite(suite_id: str) -> EvaluationSuite | None:
    return next((suite for suite in EVALUATION_SUITES if suite.id == suite_id), None)
