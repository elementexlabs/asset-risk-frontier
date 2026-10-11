"""Fixed grouped cross-fitting across years, with training-only calibration."""

from typing import Any

import numpy as np
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from frontier.register import CATEGORICAL


def logit(p: Any) -> Any:
    p = np.clip(p, 1e-8, 1 - 1e-8)
    return np.log(p / (1 - p)).reshape(-1, 1)


def preprocessor(columns: list[str]) -> Any:
    numeric = [col for col in columns if col not in CATEGORICAL]
    return ColumnTransformer(
        [
            (
                "numeric",
                Pipeline(
                    [
                        ("missing", SimpleImputer(strategy="median", add_indicator=True)),
                        ("scale", StandardScaler()),
                    ]
                ),
                numeric,
            ),
            (
                "category",
                Pipeline(
                    [
                        ("missing", SimpleImputer(strategy="most_frequent")),
                        ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                CATEGORICAL,
            ),
        ]
    )


def group_weights(groups: Any, rng: Any) -> Any:
    unique, inverse = np.unique(groups, return_inverse=True)
    counts = rng.multinomial(len(unique), np.full(len(unique), 1 / len(unique)))
    return counts[inverse].astype(float)


def calibrated_fit(
    estimator: Any,
    x: Any,
    y: Any,
    xc: Any,
    yc: Any,
    weights: Any = None,
    calibration_weights: Any = None,
) -> tuple[Any, Any]:
    if len(np.unique(y if weights is None else y[weights > 0])) != 2:
        raise ValueError("Both outcomes required in model fit")
    if len(np.unique(yc if calibration_weights is None else yc[calibration_weights > 0])) != 2:
        raise ValueError("Both outcomes required in calibration")
    estimator.fit(x, y, sample_weight=weights)
    calibration = LogisticRegression(C=1000, max_iter=1000)
    calibration.fit(logit(estimator.predict_proba(xc)[:, 1]), yc, sample_weight=calibration_weights)
    return estimator, calibration


def predict(estimator: Any, calibration: Any, x: Any) -> Any:
    return calibration.predict_proba(logit(estimator.predict_proba(x)[:, 1]))[:, 1]


def fit_folds(
    train: Any, test: Any, config: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    predictors = config["predictor_columns"]
    predictions = {
        name: np.full(len(test), np.nan) for name in ("logistic", "gradient_boosted", "prevalence")
    }
    fitted = []
    evidence = []
    for fold in range(config["folds"]):
        held = test.fold.to_numpy() == fold
        available = train.fold.to_numpy() != fold
        cal = available & (train.calibration.to_numpy() == 0)
        fit = available & ~cal
        fit_groups = set(train.loc[fit, "profile"])
        cal_groups = set(train.loc[cal, "profile"])
        test_groups = set(test.loc[held, "profile"])
        if fit_groups & cal_groups or (fit_groups | cal_groups) & test_groups:
            raise ValueError("Profile leakage between split roles")
        transform = preprocessor(predictors)
        x = transform.fit_transform(train.loc[fit, predictors])
        xc = transform.transform(train.loc[cal, predictors])
        xt = transform.transform(test.loc[held, predictors])
        y = train.loc[fit, "burned"].to_numpy(dtype=int)
        yc = train.loc[cal, "burned"].to_numpy(dtype=int)
        parameters = config["model_parameters"]
        estimators = {
            "logistic": LogisticRegression(**parameters["logistic"]),
            "gradient_boosted": HistGradientBoostingClassifier(
                **parameters["gradient_boosted"], random_state=config["seed"]
            ),
        }
        for name, estimator in estimators.items():
            estimator, calibration = calibrated_fit(estimator, x, y, xc, yc)
            predictions[name][held] = predict(estimator, calibration, xt)
            if name == config["capital_model"]:
                fitted.append(
                    {
                        "fold": fold,
                        "held": held,
                        "x": x,
                        "xc": xc,
                        "xt": xt,
                        "y": y,
                        "yc": yc,
                        "estimator": estimator,
                        "groups": train.loc[fit, "profile"].to_numpy(),
                        "cal_groups": train.loc[cal, "profile"].to_numpy(),
                    }
                )
        predictions["prevalence"][held] = float(train.loc[available, "burned"].mean())
        evidence.append(
            {
                "fold": fold,
                "fit_records": int(fit.sum()),
                "fit_failures": int(y.sum()),
                "calibration_records": int(cal.sum()),
                "calibration_failures": int(yc.sum()),
                "test_records": int(held.sum()),
                "test_failures": int(test.loc[held, "burned"].sum()),
                "fit_profiles": len(fit_groups),
                "calibration_profiles": len(cal_groups),
                "test_profiles": len(test_groups),
                "profile_overlap": 0,
            }
        )
        print(f"Fitted fold {fold + 1}/{config['folds']}", flush=True)
    if any(not np.isfinite(p).all() for p in predictions.values()):
        raise ValueError("Every test record must receive a prediction")
    return predictions, fitted, evidence


def resample_predictions(fitted: list[dict[str, Any]], count: int, seed: int, size: int) -> Any:
    rng = np.random.default_rng(seed)
    predictions = np.empty((count, size))
    # One fleet-level cluster draw shared by folds preserves dependence from
    # their overlapping earlier-year fitting and calibration sets.
    all_groups = np.unique(
        np.concatenate([fit[key] for fit in fitted for key in ("groups", "cal_groups")])
    )
    for repeat in range(count):
        counts = rng.multinomial(len(all_groups), np.full(len(all_groups), 1 / len(all_groups)))
        for fit in fitted:
            estimator = clone(fit["estimator"])
            estimator, calibration = calibrated_fit(
                estimator,
                fit["x"],
                fit["y"],
                fit["xc"],
                fit["yc"],
                counts[np.searchsorted(all_groups, fit["groups"])].astype(float),
                counts[np.searchsorted(all_groups, fit["cal_groups"])].astype(float),
            )
            predictions[repeat, fit["held"]] = predict(estimator, calibration, fit["xt"])
        if (repeat + 1) % 10 == 0:
            print(f"Failure-model resample {repeat + 1}/{count}", flush=True)
    return predictions
