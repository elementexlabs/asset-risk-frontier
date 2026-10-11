"""Render research documents from frozen numerical outputs, never hand-edit numbers."""

import html
import json
import textwrap
from pathlib import Path
from typing import Any


def estimate(metric: dict[str, Any], digits: int = 3) -> str:
    a, b = metric["interval"]
    return f"{metric['estimate']:.{digits}f} [{a:.{digits}f}, {b:.{digits}f}]"


def table(headers: list[str], rows: list[list[str]]) -> str:
    return "\n".join(
        ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
        + ["| " + " | ".join(row) + " |" for row in rows]
    )


def minimal_pdf(pages: list[str], destination: Path) -> None:
    """Five fixed text pages, standard PDF font, no external renderer or network."""
    objects: list[bytes] = []

    def add(value: bytes) -> int:
        objects.append(value)
        return len(objects)

    add(b"<< /Type /Catalog /Pages 2 0 R >>")
    add(b"")
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
    page_ids = []
    for number, page in enumerate(pages, 1):
        lines = []
        for line in page.splitlines():
            line = line.replace("**", "").replace("`", "").lstrip("# ")
            lines.extend(textwrap.wrap(line, width=88, break_long_words=True) or [""])
        if len(lines) > 66:
            raise ValueError(f"Technical note page {number} exceeds legible page capacity")
        commands = ["BT /F1 10 Tf 44 800 Td 11.2 TL"]
        for line in lines:
            safe = (
                line.encode("ascii", "replace")
                .decode()
                .replace("\\", "\\\\")
                .replace("(", "\\(")
                .replace(")", "\\)")
            )
            commands.append(f"({safe}) Tj T*")
        commands += [
            "ET",
            f"BT /F1 9 Tf 44 35 Td (Technical note - page {number} of {len(pages)}) Tj ET",
        ]
        content = "\n".join(commands).encode()
        stream = add(
            b"<< /Length "
            + str(len(content)).encode()
            + b" >>\nstream\n"
            + content
            + b"\nendstream"
        )
        page_ids.append(
            add(
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 {font} 0 R >> >> /Contents {stream} 0 R >>".encode()
            )
        )
    objects[1] = (
        f"<< /Type /Pages /Count {len(pages)} /Kids [{' '.join(f'{i} 0 R' for i in page_ids)}] >>".encode()
    )
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, value in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{i} 0 obj\n".encode() + value + b"\nendobj\n")
    start = len(data)
    data.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()
    )
    destination.write_bytes(data)


def publish(root: Path) -> None:
    out = root / "outputs"
    evaluation = json.loads((out / "evaluation.json").read_text())
    frontier = json.loads((out / "frontier.json").read_text())
    audit = json.loads((out / "audit.json").read_text())
    sensitivity = json.loads((out / "ranking-sensitivity.json").read_text())
    config = json.loads((root / "config/study.json").read_text())
    manifest = json.loads((root / "data/manifest.json").read_text())
    rows = []
    for name, model in evaluation["models"].items():
        m = model["metrics"]
        rows.append(
            [
                name,
                estimate(m["auc"]),
                estimate(m["brier"]),
                estimate(m["ece"]),
                estimate(m["precision_top_0.01"]),
                estimate(m["precision_top_0.05"]),
                estimate(m["precision_top_0.1"]),
            ]
        )
    metrics_table = table(
        ["Method", "AUC", "Brier", "ECE", "Top 1% precision", "Top 5%", "Top 10%"], rows
    )
    frontier_rows = [
        [
            f"{p['spend_cad']:,}",
            f"{p['risk_reduction']:.1f}",
            f"[{p['fixed_plan_interval'][0]:.1f}, {p['fixed_plan_interval'][1]:.1f}]",
            str(p["refurbishments"]),
            str(p["replacements"]),
        ]
        for p in frontier
    ]
    frontier_table = table(
        [
            "Spend, assumed CAD",
            "Reduction, customer-interruption proxy",
            "95% interval",
            "Refurbish",
            "Replace",
        ],
        frontier_rows,
    )
    difference = evaluation["paired_auc_difference"]
    winner = difference["winner"]
    denominator = f"{evaluation['records']:,} test records, {evaluation['failures']:,} annual burned labels and {evaluation['profiles']:,} predictor profiles"
    limits = (
        "Age-only and health-index evaluation and replacement rules are unavailable because the source has no age, installation date or measured condition inputs. "
        "Selected published CNAIM equations are implemented and tested, but there is no calibrated CNAIM fleet result. "
        "Annual burn labels do not establish condition-based failure mechanisms. "
        "Feature timestamps and asset identities are undocumented. The evaluation is retrospective, with disjoint observed predictor profiles; it is not a verified prospective failure forecast. "
        "Costs and intervention effects are scenario assumptions, so the frontier is a research result on a public register, not asset-management advice."
    )
    readme = f"""# ElementeX asset risk frontier

A reproducible research study of an entire public distribution-transformer register. Asset management depends on both ranking likely failures and deciding which interventions offer the greatest reduction in consequences within a budget. This project exposes those calculations, their uncertainty and the evidence needed to use them responsibly.

**Partial research result:** the source supports annual burned-transformer classification and a conditional capital scenario. It cannot support an age or condition-health comparison. {limits}

## Data and scope

Source: [Cauca distribution-transformer dataset, version {manifest["version"]}](https://data.mendeley.com/datasets/yzyj46xpmy/4), DOI {manifest["doi"]}. The landing page describes roughly 16,000 transformers across 42 municipalities. Each supplied annual workbook actually has {audit["2019"]["records"]:,} records. No municipality or feeder identifier is supplied. The complete source files are included, unmodified, under CC BY 4.0; see [DATA.md](DATA.md) for verbatim attribution and licence, field names, sizes and hashes.

## Evaluation

{denominator}. Earlier-year fitting and calibration use disjoint profile groups in each fold; every later-year record gets one held-out prediction. No row sampling is used for the point results. Intervals are 95% percentile intervals from {evaluation["bootstrap_valid"]} valid test-profile resamples. They condition on fitted models. Top-k inspection denominators are {", ".join(str(v) for v in evaluation["models"]["logistic"]["top_k_denominators"].values())}. See [evaluation.json](outputs/evaluation.json), [split evidence](outputs/split-evidence.json) and [scores](outputs/scores-2020.csv).

{metrics_table}

**AUC comparison: {winner}.** Paired gradient-boosted minus logistic AUC: {estimate(difference)}. Calibration and inspection precision answer different questions; no single metric establishes operational superiority. Age alone cannot be compared because age is absent. A constant training-prevalence comparator is supplied instead, explicitly labelled.

## Conditional capital frontier

Risk = calibrated logistic probability of an annual burn label times the source number of users. Its unit is a customer-interruption proxy per year; outage duration, safety, environmental loss, lost load and money valuation are not available. The logistic model was chosen for capital calculations before scoring, independently of the test comparison. Each record remains eligible in the complete planning register.

Assumed costs are CAD {config["costs"]["refurbishment"]:,} for refurbishment and CAD {config["costs"]["replacement"]:,} for replacement. Assumed risk reductions are {config["intervention_effects"]["refurbishment"]:.0%} and {config["intervention_effects"]["replacement"]:.0%}, respectively. These are illustrative constant-cost, one-year scenarios, not quotations or estimated causal effects. At most one final action is selected per record. An exact concave-increment allocation optimises this particular scenario. Intervals use {config["failure_model_bootstraps"]} refits of the failure model and its calibration, resampling earlier-year profiles with fixed preprocessing and a fixed planning register. Costs, effects and consequences are not resampled.

{frontier_table}

The displayed intervals evaluate the fixed point-estimate plan. [frontier.json](outputs/frontier.json) also contains reoptimised-resample intervals and replacement-only rules ordered by probability, users and probability times users. Age-based and health-index-only replacement are unavailable. [Interventions](outputs/interventions.csv) identify every chosen source row. Budgets are independent scenarios; benefits are not accumulated across future years.

## Register audit

Across the supplied columns, missing, invalid binary, negative, noninteger-user and maximum-below-average checks have the counts in [audit.json](outputs/audit.json). They do not validate information the source never recorded. Exact repeated-row excess is {audit["2019"]["exact_duplicate_excess"]} in the earlier register and {audit["2020"]["exact_duplicate_excess"]} in the test register. Without identities these are attribute duplicates, so no rows are removed. All equal predictor profiles are assigned together.

The network-length field reaches 717,125 despite a kilometres header. The declared plausibility threshold flags {audit["2020"]["issue_counts"]["suspect_network_length_over_100_km"]} test records above 100 km; that threshold is an assumption, not a verified physical limit. The field is excluded from headline predictors. [ranking-sensitivity.json](outputs/ranking-sensitivity.json) quantifies including it under identical splits. Missing age and condition make {audit["2020"]["health_unavailable"]:,} health rankings unavailable. Every row's quality flags remain in the output CSVs.

## Rebuild and validation

Python 3.11. Install the pinned dependencies once from PyPI, then run the full build without network:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m frontier.study
.venv/bin/python scripts/verify.py
```

The single study command checks frozen input hashes, writes fixed splits before scoring, fits both models, resamples uncertainty, optimises the frontier and regenerates every number in this README, the five-page [technical note](docs/TECHNICAL_NOTE.md), its [PDF](docs/TECHNICAL_NOTE.pdf) and the accessible [static project page](docs/site/index.html). Seeds and parameters are in [config/study.json](config/study.json). Output checksums are in [SHA256SUMS](outputs/SHA256SUMS). Runtime versions are recorded in [provenance.json](outputs/provenance.json). Replay instructions and a verified receipt are in [REPLAY.md](docs/REPLAY.md).

```sh
.venv/bin/ruff check frontier scripts tests
.venv/bin/ruff format --check frontier scripts tests
.venv/bin/mypy frontier scripts
.venv/bin/python -m pytest --basetemp=work-tmp/pytest
```

CI performs these checks on small fixtures, with networking disabled during checks, and verifies tracked frozen outputs. The full study is run locally for the release package. Cross-platform floating-point libraries can alter final digits; byte-identical replay is verified on the recorded local runtime, not promised universally.

Code: Apache-2.0. Data: CC BY 4.0. See LICENSE, NOTICE and CITATION.cff. Local preparation only; publication requires the Director's release check.
"""
    (root / "README.md").write_text(readme)
    # Five explicit pages. The Markdown and fixed-page PDF use the same content.
    pages = [
        f"""# Technical note: public fleet and evidence boundary

## Page 1: question, licence and estimand

This study asks whether supplied attributes distinguish distribution-transformer records with annual burn labels, and what an assumed intervention budget buys in customer-interruption risk. The complete public register is used. It does not estimate the treatment effect of maintenance, diagnose individual equipment or recommend a utility capital plan.

The source is Mendeley Data version {manifest["version"]}, DOI {manifest["doi"]}, published 17 September 2021. The creators are Diego A Bravo M, Carlos Lozano and Laura Alvarez. The source assigns Creative Commons Attribution 4.0 International. DATA.md contains the attribution and source licence description verbatim, plus the complete public licence. Raw workbooks are unmodified; derived tables and renamed fields are modifications. No endorsement is implied. Source metadata, file sizes, hashes and exact headers are frozen in data/manifest.json.

The landing page describes an approximately 16,000-transformer register covering 42 municipalities. Both annual files contain {audit["2019"]["records"]:,} source records with 16 fields. The earlier file has {audit["2019"]["failures"]} burned labels and the test file has {audit["2020"]["failures"]}. These are annual binary labels, with no individual failure dates. Every record is preserved, including anonymous repeated rows. The denominators refer to published records, not a independently verified count of distinct physical assets. Counts: outputs/audit.json; schemas: data/manifest.json.

The classification estimand is the conditional probability of a supplied annual burn label given the permitted attributes. Power, protection, lightning exposure, connectors, client and installation types, users, overhead-network and circuit-queue flags are predictors. The LOCATION field is binary; it is not a municipality key. Burning rate is excluded because its observation window is undefined and it may encode the target. Derived criticality and unsupplied energy are also excluded because their construction or temporal availability is unclear. Network length is excluded because its units need verification. Predictor choices: config/study.json.

No installation dates, ages, identities, feeder keys or observed condition measurements are provided. Consequently age-only, condition-health and survival-time comparisons are unavailable. The study does not invent those inputs or reinterpret the annual label as a condition measurement. Undocumented feature timestamps prevent a prospective forecast claim even after grouped validation. These boundaries govern both the evaluation and the capital scenario.
""",
        f"""# Technical note: published method and validation design

## Page 2: health kernel and leakage controls

Selected CNAIM v2.1 equations are independently implemented in frontier/health.py from the Ofgem publication dated 1 April 2021. The source is DNO Common Network Asset Indices Methodology, sections 6.1.1 and 6.1.4-7, equations 3-9 and table 5. Source document: https://www.ofgem.gov.uk/sites/default/files/docs/2021/04/dno_common_network_asset_indices_methodology_v2.1_final_01-04-2021.pdf

The kernel adjusts expected life by supplied location and duty factors, derives an exponential initial score with the published age cap, applies condition and reliability factors, then cap and collar in the specified order. It supplies health bands and the cubic annual functional-failure curve. Callers must supply justified life and calibrated modifiers; the kernel is a selected-method implementation rather than a complete category-specific CNAIM implementation. Tests check missing-age refusal, boundaries, cap-before-collar and the constant low-health failure curve. No foreign calibration is silently applied to this register. The annual burn endpoint differs from CNAIM functional failure; no equivalence is claimed.

The study protocol was committed before scoring, and revised before scoring to exclude unverified length units. The fixed seed is {config["seed"]}. Canonical permitted predictor profiles are hashed, with {config["folds"]} deterministic folds. The secondary hash segment marks training-only calibration groups. Within each fold, models fit earlier-year records outside the held profile fold; calibration uses a disjoint subset of those earlier-year groups. Later-year records in the held fold are scored once. The split rule and model parameters are in config/study.json; every record assignment is in outputs/splits.csv, written before fitting.

All profiles shared across the two annual files stay in the same held fold. Fit, calibration and test profile overlaps are zero for each fold, as verified in outputs/split-evidence.json. This prevents memorising an identical observed profile from the earlier-year register. It is stronger than treating worksheet row order as identity. It cannot rule out one physical asset changing its profile, or correlation among different records on an unidentified feeder. Location and feeder block validation are unavailable. No random row split or assumed asset matching is used.

Numerical imputation, scaling and categorical encoding are fitted only on fitting records. The models are regularised logistic classification and histogram gradient-boosted classification with fixed hyperparameters. Calibration fits logistic regression on raw log-odds using only the separate earlier-year calibration outcomes. A constant earlier-year prevalence comparator is also scored. No test outcomes choose features, tune models, calibrate probabilities or choose the capital model. The entire later-year register receives held-out predictions; the folds are cross-fitting partitions, not a sampled fleet.
""",
        f"""# Technical note: discrimination, calibration and inspection

## Page 3: evaluation results and uncertainty

Evaluation uses {denominator}. Source: outputs/evaluation.json. The yearly outcome frequency changes, so calibration learned earlier need not remain correct later. Probabilities represent the annual label association, conditional on permitted attributes, rather than guaranteed future failure frequencies.

"""
        + "\n".join(
            f"{name}: AUC {estimate(model['metrics']['auc'])}; Brier {estimate(model['metrics']['brier'])}; ECE {estimate(model['metrics']['ece'])}."
            for name, model in evaluation["models"].items()
        )
        + f"""

AUC measures pairwise discrimination, Brier measures squared probability error, and expected calibration error uses fixed probability bins. Lower Brier and ECE are better. The naive comparator is training prevalence, not age. Age performance remains unknown. Every point estimate and interval is available in outputs/evaluation.json, with calibration-bin counts, failures, mean probabilities and observed-rate intervals. Empty bins are null rather than evidence of calibration.

The paired AUC difference, gradient boosted minus logistic, is {estimate(difference)}. The prespecified AUC decision is: {winner}. A winner is reported only when the paired difference interval excludes zero; otherwise the evidence does not separate the two models. Test metrics do not select the capital model. Logistic classification was declared for planning before model scoring. Source: config/study.json and outputs/evaluation.json.

Inspection budgets select the highest probability records, with stable source-row tie order independent of outcome. The top fractions use ceil of the fraction times the test-register size; inspection denominators are {", ".join(str(v) for v in evaluation["models"]["logistic"]["top_k_denominators"].values())}. Logistic precisions are {", ".join(estimate(evaluation["models"]["logistic"]["metrics"][f"precision_top_{fraction:g}"]) for fraction in config["inspection_fractions"])}, respectively. Selection is a ranking assessment, not evidence that inspecting those records prevents failures. Source: outputs/evaluation.json and outputs/scores-2020.csv.

All displayed intervals are percentile 95% bootstrap intervals. Metric intervals resample later-year predictor profiles as clusters, retaining all records inside each sampled profile; the same draws support paired comparisons. There are {evaluation["bootstrap_valid"]} valid resamples. Predictions remain fixed, so these intervals describe test-register sampling uncertainty conditional on fitted models. They do not include uncertainty from model fitting, unidentified feeders, label errors or unrecorded feature timestamps. Calibration-bin denominators vary by draw and valid counts are recorded. The group scheme controls observed-profile leakage only, and should not be read as a complete dependence model.
""",
        f"""# Technical note: risk and assumed capital allocation

## Page 4: frontier and mathematical scope

Risk for a record equals its calibrated logistic annual-label probability times the source number of users. The total is a customer-interruption proxy, with no assumed outage duration or monetary loss. Users enter as supplied counts, not as a derived lost-load estimate. This excludes safety, environmental and restoration consequences. Source scores: outputs/scores-2020.csv; interval scope: outputs/provenance.json.

The scenario assumes refurbishment costs CAD {config["costs"]["refurbishment"]:,} and replacement CAD {config["costs"]["replacement"]:,}. Assumed reductions are {config["intervention_effects"]["refurbishment"]:.0%} and {config["intervention_effects"]["replacement"]:.0%}. These are labelled assumptions, not public price evidence or empirically identified treatment effects. They were fixed before scoring in config/study.json. All budget points are independent one-year scenarios; there is no forecast of deterioration, recurring benefit, discounting or multi-year asset transition.

For these equal-unit costs and diminishing benefits, refurbishment supplies a first increment of benefit and replacement supplies an additional smaller increment at the same marginal cost. Sorting all marginal increments gives an exact optimum: an asset's second increment cannot precede its more valuable first increment. Integer budgets buy only whole increments; unused budget remains unspent. No record gets incompatible final actions. This proof depends on the stated equal costs, homogeneous effects and additive risk. It does not generalise to arbitrary engineering project costs or interacting failures. The implementation is frontier/capital.py; small exhaustive tests compare every feasible action combination.

"""
        + "\n".join(
            f"Spend CAD {p['spend_cad']:,}: reduction {p['risk_reduction']:.1f}, interval [{p['fixed_plan_interval'][0]:.1f}, {p['fixed_plan_interval'][1]:.1f}]; refurbish {p['refurbishments']}, replace {p['replacements']}."
            for p in frontier
        )
        + f"""

These numerical points use the complete {evaluation["records"]:,}-record planning register. Source: outputs/frontier.json; chosen source rows: outputs/interventions.csv. The file also compares probability-only, users-only and risk-based replacement rules. Age and health replacement rules are unavailable, not approximated by these other rules.

Frontier intervals refit the declared failure model and training-only calibration on {config["failure_model_bootstraps"]} independently resampled earlier-year profile sets, keeping preprocessing fixed. Displayed bounds evaluate each fixed point-estimate plan under those model draws. Separate reoptimised bounds refit the plan for each draw. Both condition on the later-year register. Neither resamples costs, effects, consequence counts or causal assumptions; a narrow interval does not validate those assumptions.
""",
        f"""# Technical note: register audit, ranking impact and replay

## Page 5: quality, reproducibility and remaining work

The register audit checks missing fields, nonbinary flags, nonpositive power, negative numeric exposures, noninteger users, maximum lightning density below average and zero-user records. Across these checks the earlier register has {audit["2019"]["rows_with_any_issue"]} records with any flagged issue and the later register has {audit["2020"]["rows_with_any_issue"]}. The count includes the separate network-length plausibility flag. Exact issue-by-issue counts and denominators are in outputs/audit.json. Row-level flags are in outputs/quality-flags-2019.csv and outputs/quality-flags-2020.csv. Passing supplied-field checks does not establish trustworthy identities, dates, units or completeness of unrecorded condition information.

Exact duplicate excess is {audit["2019"]["exact_duplicate_excess"]} earlier and {audit["2020"]["exact_duplicate_excess"]} later; {audit["2020"]["rows_in_exact_duplicate_sets"]} later records lie in exact repeated-row sets. There are {audit["2020"]["repeated_profile_excess"]} excess repeated predictor profiles and {audit["2020"]["profiles_with_mixed_outcomes"]} profiles with mixed labels. These can be distinct transformers with identical recorded attributes. No anonymous record is deleted or counted as a verified duplicate asset. Profiles control splitting and bootstrap clustering; deterministic tie order selects among equal ranks. Counts: outputs/audit.json.

Network lengths above the declared 100 km plausibility threshold occur in {audit["2020"]["issue_counts"]["suspect_network_length_over_100_km"]} later records. Source maximum 717,125 suggests unverified units. No divisor or unit correction is invented. Excluding this field is the prespecified headline choice. Including it with the identical split assignments replaces {sensitivity["top_k_changes"]["logistic_0.01"]["replaced_in_top_k"]} of the top {sensitivity["top_k_changes"]["logistic_0.01"]["inspection_records"]} logistic inspection records; rank correlation is {sensitivity["logistic"]["rank_spearman"]:.3f}. All inspection-budget changes for both models are in outputs/ranking-sensitivity.json. Quality flags and their overlap with probability rankings are in outputs/audit.json.

Missing age and condition affect every one of the {audit["2020"]["health_unavailable"]:,} later records. This prevents an empirical health ranking, an age baseline, both requested replacement comparators and a condition-risk validation. These are unfinished requirements because the required source fields do not exist, not because synthetic substitutes have been accepted. Failure dates, longitudinal identity, input observation dates, independently measured intervention effects and locally justified consequence and cost models are also needed before operational translation.

One command, python -m frontier.study, rebuilds the entire analysis without network from the included raw files and pinned protocol. Frozen byte sizes and SHA-256 values are verified before reading. Splits are emitted before scoring. Seeds, runtime versions and interval scopes are in outputs/provenance.json; every generated output is covered by outputs/SHA256SUMS. Fixture tests cover leakage separation, calibration roles, bad outcomes, missing age and budget optimality. CI runs lint, types, offline fixtures and checksum verification. A local clean-checkout replay receipt with commands and exit codes is maintained in docs/REPLAY.md. The complete release package remains local pending the Director's release check.
""",
    ]
    (root / "docs/TECHNICAL_NOTE.md").write_text(
        '\n\n<div style="page-break-after: always"></div>\n\n'.join(pages) + "\n"
    )
    minimal_pdf(pages, root / "docs/TECHNICAL_NOTE.pdf")
    site = root / "docs/site"
    site.mkdir(exist_ok=True)
    header_cells = ["Method", "AUC (95% interval)", "Brier", "Top 1% precision"]
    html_rows = []
    for name, model in evaluation["models"].items():
        html_rows.append(
            '<tr><th scope="row">'
            + html.escape(name)
            + "</th>"
            + "".join(
                f"<td>{html.escape(estimate(model['metrics'][key]))}</td>"
                for key in ("auc", "brier", "precision_top_0.01")
            )
            + "</tr>"
        )
    point_rows = "".join(
        f"<tr><th scope='row'>{p['spend_cad']:,}</th><td>{p['risk_reduction']:.1f}</td><td>{p['fixed_plan_interval'][0]:.1f} to {p['fixed_plan_interval'][1]:.1f}</td><td>{p['refurbishments']}</td><td>{p['replacements']}</td></tr>"
        for p in frontier
    )
    xmax = max(p["spend_cad"] for p in frontier)
    ymax = max(p["fixed_plan_interval"][1] for p in frontier) * 1.1

    def coordinates(p: dict[str, Any], value: float) -> tuple[float, float]:
        return 80 + 660 * p["spend_cad"] / xmax, 290 - 235 * value / ymax

    points = " ".join(
        f"{coordinates(p, p['risk_reduction'])[0]:.2f},{coordinates(p, p['risk_reduction'])[1]:.2f}"
        for p in frontier
    )
    errors = "".join(
        f"<line x1='{coordinates(p, 0)[0]:.2f}' x2='{coordinates(p, 0)[0]:.2f}' y1='{coordinates(p, p['fixed_plan_interval'][0])[1]:.2f}' y2='{coordinates(p, p['fixed_plan_interval'][1])[1]:.2f}' stroke='#236660' stroke-width='3'/>"
        for p in frontier
    )
    site_html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ElementeX | Asset risk frontier</title><link rel="stylesheet" href="style.css"></head>
<body><a class="skip" href="#main">Skip to research results</a><header><a class="brand" href="#main">ElementeX Labs</a><nav aria-label="Page sections"><a href="#evaluation">Evaluation</a><a href="#capital">Capital scenario</a><a href="#quality">Register quality</a></nav></header>
<main id="main"><p class="eyebrow">Open asset-management research / Cauca public register</p><h1>What does a capital budget buy in risk reduction?</h1><p class="lead">An entire public transformer register, explicit assumptions and uncertainty you can inspect.</p>
<aside class="boundary" aria-label="Evidence boundary"><strong>Partial research result</strong><p>{html.escape(limits)}</p></aside>
<div class="facts"><p><strong>{evaluation["records"]:,}</strong><span>records per annual file</span></p><p><strong>{evaluation["failures"]}</strong><span>test-year burned labels</span></p><p><strong>{config["failure_model_bootstraps"]}</strong><span>failure-model refits for frontier bounds</span></p></div>
<section id="evaluation"><h2>Annual-label ranking</h2><p>{html.escape(denominator)}. Every test record has a prediction from a model fitted on disjoint earlier-year predictor profiles. Metric intervals condition on fitted models.</p><p><strong>AUC comparison: {html.escape(winner)}.</strong> Age and condition-health comparisons are unavailable. The prevalence comparator uses earlier-year outcomes only.</p>
<div class="table-wrap" tabindex="0" role="region" aria-label="Evaluation table"><table><caption>Evaluation with 95% profile-bootstrap intervals; source: evaluation.json</caption><thead><tr>{"".join(f'<th scope="col">{h}</th>' for h in header_cells)}</tr></thead><tbody>{"".join(html_rows)}</tbody></table></div></section>
<section id="capital"><h2>Conditional risk frontier</h2><p>Probability times users measures a customer-interruption proxy. Refurbishment and replacement costs and effects are assumptions. Each budget is an independent annual scenario on the entire test register.</p>
<figure><svg viewBox="0 0 800 350" role="img" aria-labelledby="chart-title chart-desc"><title id="chart-title">Risk reduction against assumed spend</title><desc id="chart-desc">The curve rises with spending. Vertical lines show 95% failure-model resampling bounds for each fixed plan. Exact values are in the table below.</desc><path d="M80 40V290H750" fill="none" stroke="#6c757a"/><polyline points="{points}" fill="none" stroke="#236660" stroke-width="4"/>{errors}<text x="80" y="325">0</text><text x="530" y="325">{xmax / 1000000:g} million assumed CAD</text><text x="85" y="28">Customer-interruption proxy reduction</text></svg><figcaption>Fixed-plan model-estimation bounds. Costs, causal effects and consequence uncertainty are outside these intervals.</figcaption></figure>
<div class="table-wrap" tabindex="0" role="region" aria-label="Frontier table"><table><caption>Complete-register scenario; source: frontier.json</caption><thead><tr><th scope="col">Spend, assumed CAD</th><th scope="col">Risk reduction</th><th scope="col">95% interval</th><th scope="col">Refurbish</th><th scope="col">Replace</th></tr></thead><tbody>{point_rows}</tbody></table></div></section>
<section id="quality"><h2>A register audit changes the interpretation</h2><p>{audit["2020"]["exact_duplicate_excess"]} excess identical rows are retained because physical identities are absent. {audit["2020"]["issue_counts"]["suspect_network_length_over_100_km"]} length values exceed an assumed 100 km plausibility threshold. Length is excluded; its ranking impact is measured separately. All records lack age and measured condition inputs.</p></section>
<section><h2>Inspect and reproduce</h2><p>The source is licensed CC BY 4.0. Code is Apache-2.0. No tracking or remote scripts are used.</p><ul><li><a href="../TECHNICAL_NOTE.pdf">Five-page technical note</a></li><li><a href="../../README.md">Results and rebuild instructions</a></li><li><a href="../../DATA.md">Verbatim licence and attribution</a></li><li><a href="../../outputs/evaluation.json">Evaluation and denominators</a></li><li><a href="../../outputs/frontier.json">Frontier and comparator rules</a></li><li><a href="../../outputs/audit.json">Register audit</a></li><li><a href="../../outputs/ranking-sensitivity.json">Ranking sensitivity</a></li><li><a href="../../outputs/SHA256SUMS">Output checksums</a></li></ul></section></main>
<footer>ElementeX Labs Inc. / Research on a public register / Local release candidate pending the Director's check.<br>Source: Bravo M, Lozano and Alvarez (2021), DOI <a href="https://data.mendeley.com/datasets/yzyj46xpmy/4">10.17632/yzyj46xpmy.4</a>. Data modified in derived outputs; no endorsement implied.</footer></body></html>
"""
    (site / "index.html").write_text(site_html)
    (
        site / "style.css"
    ).write_text("""*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;color:#172d36;background:#f5f6f3;font:17px/1.65 system-ui,sans-serif}a{color:#175e67;text-underline-offset:.18em}a:focus-visible,[tabindex]:focus-visible{outline:3px solid #9a5100;outline-offset:4px}.skip{position:absolute;left:-9999px}.skip:focus{left:1rem;top:1rem;background:white;padding:1rem;z-index:2}header{display:flex;justify-content:space-between;gap:2rem;align-items:center;padding:1.4rem 5vw;border-bottom:1px solid #c5cece}.brand{font-weight:750;text-decoration:none}nav{display:flex;gap:1.4rem;flex-wrap:wrap}main{max-width:1120px;margin:auto;padding:4rem 5vw}h1{font-size:clamp(2.5rem,6vw,4.7rem);line-height:1.07;letter-spacing:-.035em;max-width:850px;margin:.6rem 0 1.5rem}h2{font-size:1.8rem;line-height:1.3}p{max-width:80ch}.eyebrow{font-size:.78rem;text-transform:uppercase;letter-spacing:.11em}.lead{font-size:1.3rem;max-width:55ch}.boundary{padding:1.6rem;border-left:4px solid #9a5100;background:#fff8ea;margin:2.5rem 0}.boundary p{margin:.4rem 0}.facts{display:grid;grid-template-columns:repeat(3,1fr);gap:2rem;border-bottom:1px solid #c5cece;padding:1rem 0 2rem}.facts strong{display:block;font-size:2.5rem}.facts span{font-size:.9rem}section{margin-top:4rem;scroll-margin-top:1rem}table{width:100%;border-collapse:collapse;white-space:nowrap;font-size:.85rem;font-variant-numeric:tabular-nums}th,td{text-align:right;padding:.9rem .7rem;border-bottom:1px solid #c5cece}th:first-child{text-align:left}caption{text-align:left;font-size:.86rem;margin-bottom:.8rem;color:#425c63}.table-wrap{overflow:auto}figure{margin:2rem 0;background:white;padding:1rem;border:1px solid #c5cece}svg{display:block;width:100%;height:auto;font:14px system-ui,sans-serif;fill:#172d36}figcaption{font-size:.85rem;max-width:80ch}footer{border-top:1px solid #c5cece;padding:2rem 5vw;font-size:.85rem}li{margin:.5rem 0}@media(max-width:650px){header{align-items:start;flex-direction:column}main{padding-top:2.5rem}.facts{grid-template-columns:1fr;gap:.3rem}.facts p{margin:.3rem 0}nav{font-size:.85rem;gap:1rem}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}@media print{header nav,.skip{display:none}body{background:white;font-size:10pt}main{padding:0}section{break-inside:avoid;margin-top:1rem}h1{font-size:26pt}a{color:inherit}footer{font-size:8pt}}
""")
