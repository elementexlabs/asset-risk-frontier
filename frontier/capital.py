"""Exact multiple-choice allocation for the declared equal-cost scenario."""

from typing import Any

import numpy as np


def allocate(risk: Any, budget: int, unit: int = 6000) -> Any:
    """Concave increments: refurbish at 0.6, upgrade to replacement at 0.9.

    Each increment costs one unit. Descending marginal benefit is optimal,
    since the second increment can never outrank its own first increment.
    This exact argument applies only to these costs and effect assumptions.
    """
    risk = np.asarray(risk, dtype=float)
    if budget < 0 or unit <= 0 or not np.isfinite(risk).all() or (risk < 0).any():
        raise ValueError("Invalid planning inputs")
    count = len(risk)
    values = np.concatenate((0.6 * risk, 0.3 * risk))
    # Stable index tie order places all first increments before second increments.
    order = np.argsort(-values, kind="stable")
    order = order[values[order] > 0][: budget // unit]
    actions = np.zeros(count, dtype=int)
    np.add.at(actions, order % count, 1)
    return actions


def effect(actions: Any) -> Any:
    return np.array([0, 0.6, 0.9])[actions]


def replacement_rule(score: Any, budget: int, cost: int = 12000) -> Any:
    score = np.asarray(score, dtype=float)
    actions = np.zeros(len(score), dtype=int)
    eligible = np.flatnonzero(score > 0)
    order = eligible[np.argsort(-score[eligible], kind="stable")]
    actions[order[: budget // cost]] = 2
    return actions
