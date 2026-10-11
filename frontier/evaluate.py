"""Grouped, fixed-prediction bootstrap intervals and calibration diagnostics."""

import math
from typing import Any

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


def metrics(y: Any, p: Any, fractions: list[float]) -> dict[str, float]:
    bins = np.minimum((p * 10).astype(int), 9)
    ece = sum(
        abs(float(y[bins == b].mean()) - float(p[bins == b].mean()))
        * int((bins == b).sum())
        / len(y)
        for b in range(10)
        if (bins == b).any()
    )
    result = {
        "auc": float(roc_auc_score(y, p)),
        "average_precision": float(average_precision_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
        "ece": ece,
        "observed_rate": float(y.mean()),
        "mean_probability": float(p.mean()),
    }
    order = np.argsort(-p, kind="stable")
    for fraction in fractions:
        k = max(1, math.ceil(len(y) * fraction))
        result[f"precision_top_{fraction:g}"] = float(y[order[:k]].mean())
    return result


def group_indices(groups: Any) -> list[Any]:
    _, inverse = np.unique(groups, return_inverse=True)
    order = np.argsort(inverse, kind="stable")
    return list(np.split(order, np.flatnonzero(np.diff(inverse[order])) + 1))


def interval(values: Any) -> list[float]:
    return [float(v) for v in np.quantile(values, [0.025, 0.975])]


def evaluate(
    y: Any,
    predictions: dict[str, Any],
    groups: Any,
    fractions: list[float],
    repeats: int,
    seed: int,
) -> dict[str, Any]:
    clusters = group_indices(groups)
    rng = np.random.default_rng(seed)
    samples: dict[str, list[dict[str, float]]] = {name: [] for name in predictions}
    bin_samples: dict[str, list[list[float]]] = {
        name: [[] for _ in range(10)] for name in predictions
    }
    points = {name: metrics(y, p, fractions) for name, p in predictions.items()}
    skipped = 0
    for _ in range(repeats):
        idx = np.concatenate([clusters[i] for i in rng.integers(0, len(clusters), len(clusters))])
        if len(np.unique(y[idx])) < 2:
            skipped += 1
            continue
        for name, p in predictions.items():
            samples[name].append(metrics(y[idx], p[idx], fractions))
            bins = np.minimum((p[idx] * 10).astype(int), 9)
            for b in range(10):
                if (bins == b).any():
                    bin_samples[name][b].append(float(y[idx][bins == b].mean()))
    result: dict[str, Any] = {
        "records": len(y),
        "failures": int(y.sum()),
        "profiles": len(clusters),
        "bootstrap_requested": repeats,
        "bootstrap_valid": repeats - skipped,
        "models": {},
    }
    for name, point in points.items():
        result["models"][name] = {
            "metrics": {
                key: {"estimate": value, "interval": interval([s[key] for s in samples[name]])}
                for key, value in point.items()
            },
            "top_k_denominators": {
                f"{fraction:g}": math.ceil(len(y) * fraction) for fraction in fractions
            },
            "calibration_bins": [],
        }
        p = predictions[name]
        for b in range(10):
            idx = (p >= b / 10) & ((p < (b + 1) / 10) if b < 9 else (p <= 1))
            observations = bin_samples[name][b]
            result["models"][name]["calibration_bins"].append(
                {
                    "lower": b / 10,
                    "upper": (b + 1) / 10,
                    "records": int(idx.sum()),
                    "failures": int(y[idx].sum()),
                    "mean_probability": float(p[idx].mean()) if idx.any() else None,
                    "observed_rate": float(y[idx].mean()) if idx.any() else None,
                    "observed_interval": interval(observations) if observations else None,
                    "valid_resamples": len(observations),
                }
            )
    names = ["logistic", "gradient_boosted"]
    deltas = [
        a["auc"] - b["auc"] for a, b in zip(samples[names[1]], samples[names[0]], strict=True)
    ]
    difference = points[names[1]]["auc"] - points[names[0]]["auc"]
    bounds = interval(deltas)
    winner = (
        "gradient_boosted"
        if bounds[0] > 0
        else "logistic"
        if bounds[1] < 0
        else "No clear AUC winner"
    )
    result["paired_auc_difference"] = {
        "comparison": "gradient_boosted minus logistic",
        "estimate": difference,
        "interval": bounds,
        "winner": winner,
    }
    result["unavailable"] = {
        "age_only": "No ages supplied",
        "health_index": "No ages, condition or calibrated category mapping supplied",
    }
    return result
