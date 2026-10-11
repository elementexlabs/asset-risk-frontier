# ElementeX asset risk frontier

A reproducible research study of an entire public distribution-transformer register. Asset management depends on both ranking likely failures and deciding which interventions offer the greatest reduction in consequences within a budget. This project exposes those calculations, their uncertainty and the evidence needed to use them responsibly.

**Partial research result:** the source supports annual burned-transformer classification and a conditional capital scenario. It cannot support an age or condition-health comparison. Age-only and health-index evaluation and replacement rules are unavailable because the source has no age, installation date or measured condition inputs. Selected published CNAIM equations are implemented and tested, but there is no calibrated CNAIM fleet result. Annual burn labels do not establish condition-based failure mechanisms. Feature timestamps and asset identities are undocumented. The evaluation is retrospective, with disjoint observed predictor profiles; it is not a verified prospective failure forecast. Costs and intervention effects are scenario assumptions, so the frontier is a research result on a public register, not asset-management advice. This is a research result on a public register from Cauca, Colombia; it is not engineering, investment or asset-management advice, and it has not been validated on any Canadian utility's data.

## Data and scope

Source: [Cauca distribution-transformer dataset, version 4](https://data.mendeley.com/datasets/yzyj46xpmy/4), DOI 10.17632/yzyj46xpmy.4. The landing page describes roughly 16,000 transformers across 42 municipalities. Each supplied annual workbook actually has 15,873 records. No municipality or feeder identifier is supplied. The complete source files are included, unmodified, under CC BY 4.0; see [DATA.md](DATA.md) for verbatim attribution and licence, field names, sizes and hashes.

## Evaluation

15,873 test records, 629 annual burned labels and 11,637 predictor profiles. Earlier-year fitting and calibration use disjoint profile groups in each fold; every later-year record gets one held-out prediction. No row sampling is used for the point results. Intervals are 95% percentile intervals from 400 valid test-profile resamples. They condition on fitted models. Top-k inspection denominators are 159, 794, 1588. See [evaluation.json](outputs/evaluation.json), [split evidence](outputs/split-evidence.json) and [scores](outputs/scores-2020.csv).

| Method | AUC | Brier | ECE | Top 1% precision | Top 5% | Top 10% |
| --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted | 0.730 [0.708, 0.754] | 0.039 [0.037, 0.041] | 0.014 [0.012, 0.018] | 0.182 [0.114, 0.256] | 0.223 [0.195, 0.257] | 0.160 [0.142, 0.182] |
| logistic | 0.713 [0.691, 0.738] | 0.037 [0.034, 0.040] | 0.018 [0.015, 0.021] | 0.321 [0.245, 0.403] | 0.224 [0.192, 0.260] | 0.157 [0.139, 0.177] |
| prevalence | 0.493 [0.470, 0.513] | 0.038 [0.035, 0.041] | 0.011 [0.008, 0.014] | 0.006 [0.006, 0.068] | 0.023 [0.023, 0.047] | 0.025 [0.025, 0.044] |

**AUC comparison: No clear AUC winner.** Paired gradient-boosted minus logistic AUC: 0.017 [-0.002, 0.033]. Calibration and inspection precision answer different questions; no single metric establishes operational superiority. Age alone cannot be compared because age is absent. A constant training-prevalence comparator is supplied instead, explicitly labelled.

## Conditional capital frontier

Risk = calibrated logistic probability of an annual burn label times the source number of users. Its unit is a customer-interruption proxy per year; outage duration, safety, environmental loss, lost load and money valuation are not available. The logistic model was chosen for capital calculations before scoring, independently of the test comparison. Each record remains eligible in the complete planning register.

Assumed costs are CAD 6,000 for refurbishment and CAD 12,000 for replacement. Assumed risk reductions are 60% and 90%, respectively. These are illustrative constant-cost, one-year scenarios, not quotations or estimated causal effects. At most one final action is selected per record. An exact concave-increment allocation optimises this particular scenario. Intervals use 100 refits of the failure model and its calibration, resampling earlier-year profiles with fixed preprocessing and a fixed planning register. Costs, effects and consequences are not resampled.

| Spend, assumed CAD | Reduction, customer-interruption proxy | 95% interval | Refurbish | Replace |
| --- | --- | --- | --- | --- |
| 0 | 0.0 | [0.0, 0.0] | 0 | 0 |
| 300,000 | 508.2 | [375.9, 661.4] | 42 | 4 |
| 600,000 | 816.3 | [623.9, 1039.7] | 78 | 11 |
| 1,200,000 | 1287.2 | [997.9, 1611.4] | 132 | 34 |
| 2,400,000 | 1935.1 | [1520.9, 2386.2] | 216 | 92 |
| 4,800,000 | 2809.9 | [2249.8, 3407.6] | 396 | 202 |
| 9,600,000 | 3961.4 | [3283.7, 4671.6] | 820 | 390 |

The displayed intervals evaluate the fixed point-estimate plan. [frontier.json](outputs/frontier.json) also contains reoptimised-resample intervals and replacement-only rules ordered by probability, users and probability times users. Age-based and health-index-only replacement are unavailable. [Interventions](outputs/interventions.csv) identify every chosen source row. Budgets are independent scenarios; benefits are not accumulated across future years.

## Register audit

Across the supplied columns, missing, invalid binary, negative, noninteger-user and maximum-below-average checks have the counts in [audit.json](outputs/audit.json). They do not validate information the source never recorded. Exact repeated-row excess is 78 in the earlier register and 75 in the test register. Without identities these are attribute duplicates, so no rows are removed. All equal predictor profiles are assigned together.

The network-length field reaches 717,125 despite a kilometres header. The declared plausibility threshold flags 5395 test records above 100 km; that threshold is an assumption, not a verified physical limit. The field is excluded from headline predictors. [ranking-sensitivity.json](outputs/ranking-sensitivity.json) quantifies including it under identical splits. Missing age and condition make 15,873 health rankings unavailable. Every row's quality flags remain in the output CSVs.

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

Code: Apache-2.0. Data: CC BY 4.0. See LICENSE, NOTICE and CITATION.cff.
