from __future__ import annotations

import math
from statistics import mean, stdev


Z_95 = 1.959963984540054


def wilson_interval(successes: int, total: int) -> dict[str, float | int | None]:
    """Return a bounded 95% Wilson score interval for a binomial rate."""
    if total <= 0:
        return {"estimate": None, "lower": None, "upper": None, "n": 0}
    rate = successes / total
    denominator = 1 + Z_95**2 / total
    center = (rate + Z_95**2 / (2 * total)) / denominator
    margin = Z_95 * math.sqrt(rate * (1 - rate) / total + Z_95**2 / (4 * total**2)) / denominator
    return {"estimate": rate, "lower": max(0.0, center - margin), "upper": min(1.0, center + margin), "n": total}


def mean_interval(values: list[float]) -> dict[str, float | int | None]:
    """Return a descriptive normal 95% interval for a paired mean delta."""
    if not values:
        return {"estimate": None, "lower": None, "upper": None, "n": 0}
    estimate = mean(values)
    if len(values) < 2:
        return {"estimate": estimate, "lower": None, "upper": None, "n": len(values)}
    margin = Z_95 * stdev(values) / math.sqrt(len(values))
    return {"estimate": estimate, "lower": estimate - margin, "upper": estimate + margin, "n": len(values)}


def experiment_confidence(candidate_passes: int, baseline_passes: int, total: int,
                          deltas: dict[str, list[float]], recommended_pairs: int = 10) -> dict:
    return {
        "level": .95,
        "method": "wilson_pass_rate_and_normal_paired_mean",
        "candidate_pass_rate": wilson_interval(candidate_passes, total),
        "baseline_pass_rate": wilson_interval(baseline_passes, total),
        "paired_mean_deltas": {key: mean_interval(values) for key, values in deltas.items()},
        "sample_size": total,
        "recommended_minimum_pairs": recommended_pairs,
        "sample_guidance": "sufficient_for_regression_screen" if total >= recommended_pairs else "development_signal_only",
    }
