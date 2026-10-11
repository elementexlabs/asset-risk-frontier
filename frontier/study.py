"""One offline command regenerates every numerical research output."""

import json
import os
import platform
from pathlib import Path
from typing import Any

# Set before importing numerical libraries; repeatability and bounded CPU use.
for variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ[variable] = "1"

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import sklearn  # noqa: E402
from threadpoolctl import threadpool_limits  # noqa: E402

from frontier.capital import allocate, effect, replacement_rule  # noqa: E402
from frontier.evaluate import evaluate, interval  # noqa: E402
from frontier.models import fit_folds, resample_predictions  # noqa: E402
from frontier.register import audit, digest, issue_masks, profiles, read_register, sanitise  # noqa: E402


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def build(root: Path) -> None:
    free = os.statvfs(root.anchor or "/")
    if free.f_bavail * free.f_frsize < 25_000_000_000:
        raise RuntimeError("Free space below 25 GB: stop")
    config_path = root / "config/study.json"
    config = json.loads(config_path.read_text())
    manifest = json.loads((root / "data/manifest.json").read_text())
    if manifest["status"] != "PASS":
        raise ValueError("Data gate is not satisfied")
    out = root / "outputs"
    out.mkdir(exist_ok=True)
    frames = {}
    audits = {}
    splits = []
    for year, source in zip((2019, 2020), manifest["files"], strict=True):
        path = root / source["path"]
        if path.stat().st_size != source["bytes"] or digest(path) != source["sha256"]:
            raise ValueError("Frozen input checksum mismatch")
        raw = read_register(path, year, source["fields"])
        if len(raw) != source["records"]:
            raise ValueError("Full register denominator mismatch")
        audits[str(year)] = audit(raw, config["predictor_columns"])
        frame = sanitise(raw)
        frame["profile"] = profiles(frame, config["predictor_columns"])
        frame["fold"] = [int(p[:8], 16) % config["folds"] for p in frame.profile]
        frame["calibration"] = [
            int(p[8:16], 16) % config["calibration_modulus"] for p in frame.profile
        ]
        frames[year] = frame
        splits.append(frame[["record", "year", "profile", "fold", "calibration"]])
        flags = pd.DataFrame(issue_masks(raw)).astype(int)
        flags.insert(0, "record", raw.record)
        flags.to_csv(out / f"quality-flags-{year}.csv", index=False, lineterminator="\n")
    split_frame = pd.concat(splits, ignore_index=True)
    # Persist all assignments before fitting or examining model scores.
    split_frame.to_csv(out / "splits.csv", index=False, lineterminator="\n")
    write_json(out / "audit.json", audits)
    test = frames[2020]
    train = frames[2019]
    audits["cross_year"] = {
        "shared_predictor_profiles": len(set(train.profile) & set(test.profile)),
        "same_row_predictors": int((train.profile.to_numpy() == test.profile.to_numpy()).sum()),
        "identity_assumption": "Worksheet row correspondence is not treated as an asset identifier",
    }
    predictions, fitted, split_evidence = fit_folds(train, test, config)
    write_json(out / "split-evidence.json", split_evidence)
    results = evaluate(
        test.burned.to_numpy(dtype=int),
        predictions,
        test.profile.to_numpy(),
        config["inspection_fractions"],
        config["metric_bootstraps"],
        config["seed"],
    )
    write_json(out / "evaluation.json", results)
    # The register mixes very large lengths with fractional lengths. Preserve source
    # values; quantify ranking sensitivity to including this unverified-unit field.
    sensitivity_config = dict(config)
    sensitivity_config["predictor_columns"] = config["predictor_columns"] + ["network_km"]
    sensitivity_predictions, _, _ = fit_folds(train, test, sensitivity_config)
    sensitivity: dict[str, Any] = {
        "comparison": "Include unverified network length versus excluded headline",
        "records": len(test),
        "same_splits": True,
        "top_k_changes": {},
    }
    from scipy.stats import spearmanr

    for name in ("logistic", "gradient_boosted"):
        before = predictions[name]
        after = sensitivity_predictions[name]
        sensitivity[name] = {"rank_spearman": float(spearmanr(before, after).statistic)}
        for fraction in config["inspection_fractions"]:
            k = int(np.ceil(len(test) * fraction))
            a = set(np.argsort(-before, kind="stable")[:k])
            b = set(np.argsort(-after, kind="stable")[:k])
            sensitivity["top_k_changes"][f"{name}_{fraction:g}"] = {
                "inspection_records": k,
                "replaced_in_top_k": len(a - b),
                "overlap": len(a & b),
            }
    write_json(out / "ranking-sensitivity.json", sensitivity)
    # Users are supplied by source; invalid or missing consequence prohibits planning.
    if test.users.isna().any():
        raise ValueError(
            "Consequence unavailable on register records; cannot claim complete-fleet frontier"
        )
    consequence = test.users.to_numpy(dtype=float)
    risk = predictions[config["capital_model"]] * consequence
    record_scores = test[["record", "profile", "fold", "burned", "users"]].copy()
    for name, p in predictions.items():
        record_scores[f"probability_{name}"] = p
    record_scores["risk_customer_interruptions_proxy"] = risk
    record_scores["age_years"] = None
    record_scores["health_score"] = None
    record_scores["health_status"] = "unavailable: no age or condition inputs"
    record_scores.to_csv(
        out / "scores-2020.csv", index=False, float_format="%.12g", lineterminator="\n"
    )
    bootstrap_p = resample_predictions(
        fitted, config["failure_model_bootstraps"], config["seed"] + 1, len(test)
    )
    bootstrap_risk = bootstrap_p * consequence
    # Quantiles per asset permit inspection of model-estimation uncertainty.
    risk_intervals = pd.DataFrame(
        {
            "record": test.record,
            "risk_lower": np.quantile(bootstrap_risk, 0.025, axis=0),
            "risk_upper": np.quantile(bootstrap_risk, 0.975, axis=0),
        }
    )
    risk_intervals.to_csv(
        out / "risk-intervals-2020.csv", index=False, float_format="%.12g", lineterminator="\n"
    )
    frontier = []
    interventions: list[dict[str, Any]] = []
    for budget in config["budgets_cad"]:
        actions = allocate(risk, budget)
        benefit = float(np.dot(risk, effect(actions)))
        fixed_draws = bootstrap_risk @ effect(actions)
        reoptimised = [float(np.dot(r, effect(allocate(r, budget)))) for r in bootstrap_risk]
        strategies = {}
        for name, ranking in {
            "probability_only": predictions["logistic"],
            "users_only": consequence,
            "risk_replacement_only": risk,
        }.items():
            alternative = replacement_rule(ranking, budget)
            strategies[name] = {
                "spend_cad": int(alternative.sum()) * 6000,
                "replacements": int((alternative == 2).sum()),
                "risk_reduction": float(np.dot(risk, effect(alternative))),
                "interval": interval(bootstrap_risk @ effect(alternative)),
            }
        frontier.append(
            {
                "budget_cad": budget,
                "spend_cad": int(actions.sum()) * 6000,
                "refurbishments": int((actions == 1).sum()),
                "replacements": int((actions == 2).sum()),
                "risk_reduction": benefit,
                "fixed_plan_interval": interval(fixed_draws),
                "reoptimised_interval": interval(reoptimised),
                "baseline_risk": float(risk.sum()),
                "reduction_fraction": benefit / float(risk.sum()),
                "register_records": len(test),
                "valid_model_resamples": len(bootstrap_risk),
                "comparators": strategies,
                "unavailable_comparators": ["age_based", "health_index_only"],
            }
        )
        interventions.extend(
            {
                "budget_cad": budget,
                "record": record,
                "action": "replace" if a == 2 else "refurbish",
                "cost_cad": int(a) * 6000,
            }
            for record, a in zip(test.record, actions, strict=True)
            if a
        )
    write_json(out / "frontier.json", frontier)
    pd.DataFrame(interventions).to_csv(out / "interventions.csv", index=False, lineterminator="\n")
    # Same complete register, perturb flagged nonconsequence predictors without changing the cohort.
    flags = pd.read_csv(out / "quality-flags-2020.csv").drop(columns=["record"])
    any_issue = flags.to_numpy().any(axis=1)
    audits["ranking_effects"] = {
        "flagged_test_records": int(any_issue.sum()),
        "flagged_test_risk": float(risk[any_issue].sum()),
        "complete_records_scored": len(test),
        "duplicate_records_removed": 0,
        "unavailable_age_ranks": len(test),
        "unavailable_health_ranks": len(test),
    }
    for fraction in config["inspection_fractions"]:
        k = int(np.ceil(len(test) * fraction))
        idx = np.argsort(-predictions["logistic"], kind="stable")[:k]
        audits["ranking_effects"][f"flagged_in_top_{fraction:g}"] = int(any_issue[idx].sum())
    write_json(out / "audit.json", audits)
    write_json(
        out / "provenance.json",
        {
            "study_protocol_sha256": digest(config_path),
            "split_sha256": digest(out / "splits.csv"),
            "input_sha256": {s["path"]: s["sha256"] for s in manifest["files"]},
            "runtime": {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "pandas": pd.__version__,
                "scikit_learn": sklearn.__version__,
            },
            "seed": config["seed"],
            "threads": 1,
            "interval_scope": "Metric intervals resample test predictor profiles with fixed predictions. Frontier intervals refit logistic and calibration on a shared fleet-level 2019 profile draw across folds, retaining split roles, with fixed preprocessing and a fixed 2020 register. Effects, costs, consequences and missing timestamps are not quantified.",
        },
    )
    from frontier.publish import publish

    publish(root)
    paths = sorted(p for p in out.iterdir() if p.is_file() and p.name != "SHA256SUMS")
    paths += [
        root / "README.md",
        root / "docs/TECHNICAL_NOTE.md",
        root / "docs/TECHNICAL_NOTE.pdf",
        root / "docs/site/index.html",
        root / "docs/site/style.css",
    ]
    (out / "SHA256SUMS").write_text("".join(f"{digest(p)}  {p.relative_to(root)}\n" for p in paths))
    print(f"Rebuilt {len(test)} test records and {len(frontier)} budget points", flush=True)


def main() -> None:
    with threadpool_limits(limits=1):
        build(Path.cwd())


if __name__ == "__main__":
    main()
