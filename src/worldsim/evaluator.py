from __future__ import annotations


def evaluate(metrics: dict, scenario: dict) -> tuple[str, list[dict]]:
    limits = scenario["limits"]
    checks = []
    mappings = {
        "max_collisions": (metrics["collisions"], "<=", lambda actual, expected: actual <= expected),
        "max_contact_force_n": (metrics["max_contact_force_n"], "<=", lambda actual, expected: actual <= expected),
        "must_complete": (metrics["task_completed"], "==", lambda actual, expected: actual == expected),
        "max_duration_s": (metrics["sim_duration_s"], "<=", lambda actual, expected: actual <= expected),
    }
    for limit_id, (actual, operator, comparator) in mappings.items():
        definition = limits[limit_id]
        checks.append({
            "id": limit_id,
            "actual": actual,
            "operator": operator,
            "limit": definition["value"],
            "unit": definition["unit"],
            "passed": comparator(actual, definition["value"]),
            "source": definition["source"],
            "calibration_status": definition["calibration_status"],
            "rationale": definition["rationale"],
        })
    return ("pass" if all(check["passed"] for check in checks) else "fail"), checks

