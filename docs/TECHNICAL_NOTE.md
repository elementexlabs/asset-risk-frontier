# Technical note: public fleet and evidence boundary

## Page 1: question, licence and estimand

This study asks whether supplied attributes distinguish distribution-transformer records with annual burn labels, and what an assumed intervention budget buys in customer-interruption risk. The complete public register is used. It does not estimate the treatment effect of maintenance, diagnose individual equipment or recommend a utility capital plan.

The source is Mendeley Data version 4, DOI 10.17632/yzyj46xpmy.4, published 17 September 2021. The creators are Diego A Bravo M, Carlos Lozano and Laura Alvarez. The source assigns Creative Commons Attribution 4.0 International. DATA.md contains the attribution and source licence description verbatim, plus the complete public licence. Raw workbooks are unmodified; derived tables and renamed fields are modifications. No endorsement is implied. Source metadata, file sizes, hashes and exact headers are frozen in data/manifest.json.

The landing page describes an approximately 16,000-transformer register covering 42 municipalities. Both annual files contain 15,873 source records with 16 fields. The earlier file has 807 burned labels and the test file has 629. These are annual binary labels, with no individual failure dates. Every record is preserved, including anonymous repeated rows. The denominators refer to published records, not a independently verified count of distinct physical assets. Counts: outputs/audit.json; schemas: data/manifest.json.

The classification estimand is the conditional probability of a supplied annual burn label given the permitted attributes. Power, protection, lightning exposure, connectors, client and installation types, users, overhead-network and circuit-queue flags are predictors. The LOCATION field is binary; it is not a municipality key. Burning rate is excluded because its observation window is undefined and it may encode the target. Derived criticality and unsupplied energy are also excluded because their construction or temporal availability is unclear. Network length is excluded because its units need verification. Predictor choices: config/study.json.

No installation dates, ages, identities, feeder keys or observed condition measurements are provided. Consequently age-only, condition-health and survival-time comparisons are unavailable. The study does not invent those inputs or reinterpret the annual label as a condition measurement. Undocumented feature timestamps prevent a prospective forecast claim even after grouped validation. These boundaries govern both the evaluation and the capital scenario.


<div style="page-break-after: always"></div>

# Technical note: published method and validation design

## Page 2: health kernel and leakage controls

Selected CNAIM v2.1 equations are independently implemented in frontier/health.py from the Ofgem publication dated 1 April 2021. The source is DNO Common Network Asset Indices Methodology, sections 6.1.1 and 6.1.4-7, equations 3-9 and table 5. Source document: https://www.ofgem.gov.uk/sites/default/files/docs/2021/04/dno_common_network_asset_indices_methodology_v2.1_final_01-04-2021.pdf

The kernel adjusts expected life by supplied location and duty factors, derives an exponential initial score with the published age cap, applies condition and reliability factors, then cap and collar in the specified order. It supplies health bands and the cubic annual functional-failure curve. Callers must supply justified life and calibrated modifiers; the kernel is a selected-method implementation rather than a complete category-specific CNAIM implementation. Tests check missing-age refusal, boundaries, cap-before-collar and the constant low-health failure curve. No foreign calibration is silently applied to this register. The annual burn endpoint differs from CNAIM functional failure; no equivalence is claimed.

The study protocol was committed before scoring, and revised before scoring to exclude unverified length units. The fixed seed is 20261011. Canonical permitted predictor profiles are hashed, with 5 deterministic folds. The secondary hash segment marks training-only calibration groups. Within each fold, models fit earlier-year records outside the held profile fold; calibration uses a disjoint subset of those earlier-year groups. Later-year records in the held fold are scored once. The split rule and model parameters are in config/study.json; every record assignment is in outputs/splits.csv, written before fitting.

All profiles shared across the two annual files stay in the same held fold. Fit, calibration and test profile overlaps are zero for each fold, as verified in outputs/split-evidence.json. This prevents memorising an identical observed profile from the earlier-year register. It is stronger than treating worksheet row order as identity. It cannot rule out one physical asset changing its profile, or correlation among different records on an unidentified feeder. Location and feeder block validation are unavailable. No random row split or assumed asset matching is used.

Numerical imputation, scaling and categorical encoding are fitted only on fitting records. The models are regularised logistic classification and histogram gradient-boosted classification with fixed hyperparameters. Calibration fits logistic regression on raw log-odds using only the separate earlier-year calibration outcomes. A constant earlier-year prevalence comparator is also scored. No test outcomes choose features, tune models, calibrate probabilities or choose the capital model. The entire later-year register receives held-out predictions; the folds are cross-fitting partitions, not a sampled fleet.


<div style="page-break-after: always"></div>

# Technical note: discrimination, calibration and inspection

## Page 3: evaluation results and uncertainty

Evaluation uses 15,873 test records, 629 annual burned labels and 11,637 predictor profiles. Source: outputs/evaluation.json. The yearly outcome frequency changes, so calibration learned earlier need not remain correct later. Probabilities represent the annual label association, conditional on permitted attributes, rather than guaranteed future failure frequencies.

gradient_boosted: AUC 0.730 [0.708, 0.754]; Brier 0.039 [0.037, 0.041]; ECE 0.014 [0.012, 0.018].
logistic: AUC 0.713 [0.691, 0.738]; Brier 0.037 [0.034, 0.040]; ECE 0.018 [0.015, 0.021].
prevalence: AUC 0.493 [0.470, 0.513]; Brier 0.038 [0.035, 0.041]; ECE 0.011 [0.008, 0.014].

AUC measures pairwise discrimination, Brier measures squared probability error, and expected calibration error uses fixed probability bins. Lower Brier and ECE are better. The naive comparator is training prevalence, not age. Age performance remains unknown. Every point estimate and interval is available in outputs/evaluation.json, with calibration-bin counts, failures, mean probabilities and observed-rate intervals. Empty bins are null rather than evidence of calibration.

The paired AUC difference, gradient boosted minus logistic, is 0.017 [-0.002, 0.033]. The prespecified AUC decision is: No clear AUC winner. A winner is reported only when the paired difference interval excludes zero; otherwise the evidence does not separate the two models. Test metrics do not select the capital model. Logistic classification was declared for planning before model scoring. Source: config/study.json and outputs/evaluation.json.

Inspection budgets select the highest probability records, with stable source-row tie order independent of outcome. The top fractions use ceil of the fraction times the test-register size; inspection denominators are 159, 794, 1588. Logistic precisions are 0.321 [0.245, 0.403], 0.224 [0.192, 0.260], 0.157 [0.139, 0.177], respectively. Selection is a ranking assessment, not evidence that inspecting those records prevents failures. Source: outputs/evaluation.json and outputs/scores-2020.csv.

All displayed intervals are percentile 95% bootstrap intervals. Metric intervals resample later-year predictor profiles as clusters, retaining all records inside each sampled profile; the same draws support paired comparisons. There are 400 valid resamples. Predictions remain fixed, so these intervals describe test-register sampling uncertainty conditional on fitted models. They do not include uncertainty from model fitting, unidentified feeders, label errors or unrecorded feature timestamps. Calibration-bin denominators vary by draw and valid counts are recorded. The group scheme controls observed-profile leakage only, and should not be read as a complete dependence model.


<div style="page-break-after: always"></div>

# Technical note: risk and assumed capital allocation

## Page 4: frontier and mathematical scope

Risk for a record equals its calibrated logistic annual-label probability times the source number of users. The total is a customer-interruption proxy, with no assumed outage duration or monetary loss. Users enter as supplied counts, not as a derived lost-load estimate. This excludes safety, environmental and restoration consequences. Source scores: outputs/scores-2020.csv; interval scope: outputs/provenance.json.

The scenario assumes refurbishment costs CAD 6,000 and replacement CAD 12,000. Assumed reductions are 60% and 90%. These are labelled assumptions, not public price evidence or empirically identified treatment effects. They were fixed before scoring in config/study.json. All budget points are independent one-year scenarios; there is no forecast of deterioration, recurring benefit, discounting or multi-year asset transition.

For these equal-unit costs and diminishing benefits, refurbishment supplies a first increment of benefit and replacement supplies an additional smaller increment at the same marginal cost. Sorting all marginal increments gives an exact optimum: an asset's second increment cannot precede its more valuable first increment. Integer budgets buy only whole increments; unused budget remains unspent. No record gets incompatible final actions. This proof depends on the stated equal costs, homogeneous effects and additive risk. It does not generalise to arbitrary engineering project costs or interacting failures. The implementation is frontier/capital.py; small exhaustive tests compare every feasible action combination.

Spend CAD 0: reduction 0.0, interval [0.0, 0.0]; refurbish 0, replace 0.
Spend CAD 300,000: reduction 508.2, interval [375.9, 661.4]; refurbish 42, replace 4.
Spend CAD 600,000: reduction 816.3, interval [623.9, 1039.7]; refurbish 78, replace 11.
Spend CAD 1,200,000: reduction 1287.2, interval [997.9, 1611.4]; refurbish 132, replace 34.
Spend CAD 2,400,000: reduction 1935.1, interval [1520.9, 2386.2]; refurbish 216, replace 92.
Spend CAD 4,800,000: reduction 2809.9, interval [2249.8, 3407.6]; refurbish 396, replace 202.
Spend CAD 9,600,000: reduction 3961.4, interval [3283.7, 4671.6]; refurbish 820, replace 390.

These numerical points use the complete 15,873-record planning register. Source: outputs/frontier.json; chosen source rows: outputs/interventions.csv. The file also compares probability-only, users-only and risk-based replacement rules. Age and health replacement rules are unavailable, not approximated by these other rules.

Frontier intervals refit the declared failure model and training-only calibration on 100 independently resampled earlier-year profile sets, keeping preprocessing fixed. Displayed bounds evaluate each fixed point-estimate plan under those model draws. Separate reoptimised bounds refit the plan for each draw. Both condition on the later-year register. Neither resamples costs, effects, consequence counts or causal assumptions; a narrow interval does not validate those assumptions.


<div style="page-break-after: always"></div>

# Technical note: register audit, ranking impact and replay

## Page 5: quality, reproducibility and remaining work

The register audit checks missing fields, nonbinary flags, nonpositive power, negative numeric exposures, noninteger users, maximum lightning density below average and zero-user records. Across these checks the earlier register has 5395 records with any flagged issue and the later register has 5395. The count includes the separate network-length plausibility flag. Exact issue-by-issue counts and denominators are in outputs/audit.json. Row-level flags are in outputs/quality-flags-2019.csv and outputs/quality-flags-2020.csv. Passing supplied-field checks does not establish trustworthy identities, dates, units or completeness of unrecorded condition information.

Exact duplicate excess is 78 earlier and 75 later; 120 later records lie in exact repeated-row sets. There are 4236 excess repeated predictor profiles and 189 profiles with mixed labels. These can be distinct transformers with identical recorded attributes. No anonymous record is deleted or counted as a verified duplicate asset. Profiles control splitting and bootstrap clustering; deterministic tie order selects among equal ranks. Counts: outputs/audit.json.

Network lengths above the declared 100 km plausibility threshold occur in 5395 later records. Source maximum 717,125 suggests unverified units. No divisor or unit correction is invented. Excluding this field is the prespecified headline choice. Including it with the identical split assignments replaces 41 of the top 159 logistic inspection records; rank correlation is 0.977. All inspection-budget changes for both models are in outputs/ranking-sensitivity.json. Quality flags and their overlap with probability rankings are in outputs/audit.json.

Missing age and condition affect every one of the 15,873 later records. This prevents an empirical health ranking, an age baseline, both requested replacement comparators and a condition-risk validation. These are unfinished requirements because the required source fields do not exist, not because synthetic substitutes have been accepted. Failure dates, longitudinal identity, input observation dates, independently measured intervention effects and locally justified consequence and cost models are also needed before operational translation.

One command, python -m frontier.study, rebuilds the entire analysis without network from the included raw files and pinned protocol. Frozen byte sizes and SHA-256 values are verified before reading. Splits are emitted before scoring. Seeds, runtime versions and interval scopes are in outputs/provenance.json; every generated output is covered by outputs/SHA256SUMS. Fixture tests cover leakage separation, calibration roles, bad outcomes, missing age and budget optimality. CI runs lint, types, offline fixtures and checksum verification. A local clean-checkout replay receipt with commands and exit codes is maintained in docs/REPLAY.md. The complete release package remains local pending the Director's release check.

