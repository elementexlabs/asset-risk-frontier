import itertools
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from openpyxl import Workbook

from frontier.capital import allocate, effect
from frontier.evaluate import evaluate
from frontier.health import band, failure_rate, health_score
from frontier.models import fit_folds, resample_predictions
from frontier.register import COLUMNS, audit, profiles, read_register, sanitise


def fixture() -> Any:
    rng = np.random.default_rng(71)
    n = 300
    frame = pd.DataFrame(
        {
            "location": rng.integers(0, 2, n),
            "power": rng.integers(10, 100, n),
            "self_protection": rng.integers(0, 2, n),
            "ddt_average": np.ones(n),
            "ddt_maximum": np.ones(n) * 2,
            "burning_rate": rng.random(n),
            "criticality": np.zeros(n),
            "connectors": rng.integers(0, 2, n),
            "client_type": ["RESIDENTIAL"] * n,
            "users": rng.integers(1, 50, n),
            "eens": np.ones(n),
            "installation_type": ["OVERHEAD"] * n,
            "air_network": np.ones(n),
            "circuit_queue": np.zeros(n),
            "network_km": rng.random(n),
            "burned": np.arange(n) % 3 == 0,
            "record": [f"fixture:{i}" for i in range(n)],
            "year": [2019] * n,
        }
    )
    config = json.loads(Path("config/study.json").read_text())
    frame["profile"] = profiles(frame, config["predictor_columns"])
    frame["fold"] = [int(p[:8], 16) % 5 for p in frame.profile]
    frame["calibration"] = [int(p[8:16], 16) % 5 for p in frame.profile]
    return frame


def test_missing_age_is_unavailable() -> None:
    assert health_score(None, 50, 1, 1) is None


def test_published_age_curve_and_cap_order() -> None:
    assert health_score(0, 50, 1, 1) == 0.5
    assert health_score(50, 50, 1, 1) == pytest.approx(5.5)
    assert health_score(1000, 50, 1, 1) == pytest.approx(5.5)
    assert health_score(1000, 50, 1, 1, condition_factor=2, cap=3, collar=8) == 8


@pytest.mark.parametrize("score,expected", [(0.5, 1), (3, 2), (5.5, 3), (6.5, 4), (8, 5), (15, 5)])
def test_published_health_bands(score: float, expected: int) -> None:
    assert band(score) == expected


def test_failure_curve_floor_and_monotonicity() -> None:
    assert failure_rate(0.5, 0.000078) == failure_rate(4, 0.000078)
    assert failure_rate(8, 0.000078) > failure_rate(5.5, 0.000078)


@pytest.mark.parametrize("age", [-1, float("nan"), float("inf")])
def test_invalid_age_is_not_scored(age: float) -> None:
    with pytest.raises(ValueError):
        health_score(age, 50, 1, 1)


@pytest.mark.parametrize("budget", [0, 5999, 6000, 12000, 18000, 30000, 999999])
def test_optimum_against_exhaustive_actions(budget: int) -> None:
    risk = np.array([1, 3, 2, 7, 0], dtype=float)
    actions = allocate(risk, budget)
    optimum = max(
        float(np.dot(risk, effect(np.array(option))))
        for option in itertools.product(range(3), repeat=len(risk))
        if sum(option) * 6000 <= budget
    )
    assert float(np.dot(risk, effect(actions))) == pytest.approx(optimum)
    assert actions.sum() * 6000 <= budget
    assert not actions[-1]


def test_register_rejects_bad_label_and_schema(tmp_path: Path) -> None:
    path = tmp_path / "fixture.xlsx"
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.title = "Datos"
    sheet.append(COLUMNS)
    sheet.append([1] * 15 + [2])
    book.save(path)
    with pytest.raises(ValueError, match="outcome"):
        read_register(path, 2019, COLUMNS)
    with pytest.raises(ValueError, match="schema"):
        read_register(path, 2019, list(reversed(COLUMNS)))


def test_anonymous_duplicates_retained_and_invalid_inputs_flagged() -> None:
    frame = fixture().iloc[:3].copy()
    frame.loc[frame.index[1], COLUMNS] = frame.loc[frame.index[0], COLUMNS]
    frame.loc[frame.index[2], "users"] = -3
    config = json.loads(Path("config/study.json").read_text())
    result = audit(frame, config["predictor_columns"])
    assert result["exact_duplicate_excess"] == 1
    assert result["issue_counts"]["invalid_nonnegative_users"] == 1
    clean = sanitise(frame)
    assert len(clean) == len(frame)
    assert pd.isna(clean.users.iloc[2])


def test_grouped_models_do_not_see_held_out_profiles() -> None:
    train = fixture()
    test = train.copy()
    test["year"] = 2020
    config = json.loads(Path("config/study.json").read_text())
    config["model_parameters"]["gradient_boosted"]["max_iter"] = 3
    config["model_parameters"]["gradient_boosted"]["min_samples_leaf"] = 5
    predictions, fitted, evidence = fit_folds(train, test, config)
    assert all(fold["profile_overlap"] == 0 for fold in evidence)
    assert sum(fold["test_records"] for fold in evidence) == len(test)
    assert all(np.isfinite(p).all() for p in predictions.values())
    assert all(((p >= 0) & (p <= 1)).all() for p in predictions.values())
    sampled = resample_predictions(fitted, 2, 70, len(test))
    assert sampled.shape == (2, len(test))
    results = evaluate(
        test.burned.to_numpy(dtype=int), predictions, test.profile.to_numpy(), [0.05], 10, 70
    )
    assert results["bootstrap_valid"] == 10
    for model in results["models"].values():
        assert model["top_k_denominators"]["0.05"] == 15
        assert model["metrics"]["auc"]["interval"][0] >= 0


def test_protocol_excludes_outcome_derived_fields() -> None:
    config = json.loads(Path("config/study.json").read_text())
    forbidden = {"burned", "burning_rate", "eens", "criticality", "network_km", "year", "record"}
    assert not forbidden.intersection(config["predictor_columns"])
    assert config["capital_model"] == "logistic"
