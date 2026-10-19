# Jev benchmark-and-improvement experiment

<!-- agentic-run-status:start -->
**Scope update - October 19, 2026:** This report covers the initial benchmark, which found a small probability-score improvement with substantial uncertainty. Subsequent pure agentic, RL-like prompt and question-strategy optimization failed to meet the 70% accuracy objective or establish a reliable advantage over the baselines. Read [the latest run summary](question_search_10/README.md) for the ten-iteration search and later representation tests. The initial benchmark findings and saved tables below are unchanged.
<!-- agentic-run-status:end -->


Report generated 2026-10-19T15:09:58.455823+00:00. Retrospective exploratory evidence; five companies, no prospective validation.

## Finding

The selected Jev strategy was **market_plus_jev_strong**, frozen using validation results before test prices or labels were acquired. Its final-test Brier was **0.6648**, versus **0.6852** for the matched market-only predictor and **0.6795** for training class frequencies.

It achieved a lower point-estimate Brier than these baselines on this small final sample. This is tentative incremental evidence, not established predictive skill or prospective profitability.

## Dataset and exclusions

Intended 150 cases; collected **150**: 135 issuer-news items and 15 unrelated NASA astronomy controls. Source issuers: NVDA, AAPL, AMD, META and MSFT. Range: 2023-01-01 through 2025-12-31. This fixed five-company selection uses accessible primary-source archives; GOOG, TSM and TSLA were not included.

| Company | Train | Validation | Final test |
|---|---:|---:|---:|
| NVDA | 15 | 9 | 6 |
| AAPL | 15 | 9 | 6 |
| AMD | 15 | 9 | 6 |
| META | 15 | 9 | 6 |
| MSFT | 15 | 9 | 6 |

Recorded 302 source/selection exclusions: previously inspected source or nearby legacy NVIDIA event: 301; No substantive article-body selector: 1.

Each issuer's nearby releases were conservatively grouped in seven-day blocks; one article represents a block. Sampling used source dates and a fixed seeded rule, never future returns. Legacy source URLs and nearby NVIDIA dates were removed. Each case is assigned to one chronological split. Earlier cases whose target window crosses the next split are purged before freezing. No post-freeze failure is replaced.

All article bodies were retrieved during this experiment, not captured contemporaneously. **Every historical text version is marked uncertain**. Raw HTML, extraction selectors, text hashes, publication metadata and actual first-observed times are saved. Updated pages may contain later information; a historical date alone cannot resolve this. Publisher excerpts are labeled and no AI summaries substitute for source text.

Selection reserved risk/adverse-action and financial-results title categories where available, then filled with dates spread across each period. Those title categories are not return labels. Every saved model input is conservatively labeled publisher_excerpt, including uncapped body extractions. Public HTML snapshots are saved as decoded UTF-8; the HTTP-payload hash is retained separately, so newline/encoding conversion can make it differ from the local snapshot's byte hash.

Primary newsrooms have a promotional bias and limited adverse independent reporting. Unrelated controls are deliberately easy relevance checks. This is not a representative or exhaustive general-news benchmark.

**Price-label coverage:** train: {'ok': 74, 'split_in_target_window': 1}, class counts {'flat': 12, 'up': 45, 'down': 17}; validation: {'ok': 45}, class counts {'down': 15, 'up': 24, 'flat': 6}; test: {'ok': 30}, class counts {'flat': 4, 'up': 13, 'down': 13}. The frozen denominator includes every selected case.

## Frozen target and scoring

Entry is the first XNYS regular-session open strictly after the end-of-day New York cutoff. Exit is the fifth session close, counting entry as one. Return = exit close / entry open - 1. Up is above +1%, down below -1%, and flat includes both boundaries. This measures subsequent raw price movement, excluding initial overnight repricing and cash dividends; it is not causal attribution or trading profit.

Yahoo/yfinance OHLC are vendor split-adjusted, with auto_adjust=False, actions=True, repair=False. Windows with a reported split are unscored. Missing/invalid target prices are explicit failures, never interpolated. Exchange calendar handles holidays and early closes. Prices and library versions are archived.

Brier = mean(sum((class probability - one-hot observed class)^2)) across the three classes; lower is better, range 0–2. Covered-case metrics are reported alongside response and label coverage. Validation ranking charges missing forecasts loss 2, preventing failed cases from improving selection. Abstention is a separate max-probability >=0.60 policy, not the flat class.

## Baselines and complete validation experiment table

All statistical predictors, imputers and scalers were fit on training cases only. No validation refit was performed. Market features are 1/5/20-session stock and SPY returns, 20-session volatilities, and 5/20-session relative returns, using closes no later than each cutoff.

| Method | Train Brier | Validation Brier | Validation accuracy | Balanced accuracy | Forecast coverage | Selection Brier |
|---|---:|---:|---:|---:|---:|---:|
| always_up | 0.7838 | 0.9333 | 53.3% | 33.3% | 100.0% | 0.9333 |
| always_flat | 1.6757 | 1.7333 | 13.3% | 33.3% | 100.0% | 1.7333 |
| always_down | 1.5405 | 1.3333 | 33.3% | 33.3% | 100.0% | 1.3333 |
| training_prior | 0.5511 | 0.6038 | 53.3% | 33.3% | 100.0% | 0.6038 |
| market_only | 0.4970 | 0.6398 | 51.1% | 31.9% | 100.0% | 0.6398 |
| legacy | 1.2529 | 1.3210 | 15.6% | 34.7% | 100.0% | 1.3210 |
| single_direct | 1.2161 | 1.2596 | 26.7% | 41.7% | 100.0% | 1.2596 |
| shrunk_direct | 0.7291 | 0.7717 | 28.9% | 38.9% | 100.0% | 0.7717 |
| market_plus_jev | 0.4294 | 0.6698 | 48.9% | 31.4% | 100.0% | 0.6698 |
| market_only_strong | 0.5287 | 0.5929 | 53.3% | 33.3% | 100.0% | 0.5929 |
| market_plus_jev_strong | 0.5036 | 0.5892 | 53.3% | 33.3% | 100.0% | 0.5892 |

Selected Jev strategy: **market_plus_jev_strong**. Overall validation champion including baselines: **market_plus_jev_strong**. Four candidates were evaluated; no hidden search or test-driven tuning was performed.

| Iteration | Change | Previous best Jev | Retained as best Jev? |
|---|---|---|---|
| 1 | single_direct: Remove event/economics/magnitude calls; keep the same final question and source. | legacy | yes |
| 2 | shrunk_direct: Blend each direct probability 50/50 with training class frequencies. | single_direct | yes |
| 3 | market_plus_jev: Add atomic Jev features to the identical market-only logistic model, C=0.1; fit training only. | shrunk_direct | yes |
| 4 | market_plus_jev_strong: Change only C from 0.1 to 0.01; cache the same Jev judgments; also fit matched C=0.01 market-only ablation. | market_plus_jev | yes |

**Iteration 1: single_direct**

Observed issue: Legacy validation Brier=1.3210133333333334, coverage=1.0; intermediary interpretations have no learned mapping to post-opening returns.

Expected before running: Simpler orchestration may reduce propagated interpretation errors; improvement is uncertain.

**Iteration 2: shrunk_direct**

Observed issue: Single-direct mean maximum validation probability=0.7997777777777778; observed accuracy=0.26666666666666666. Forecast probabilities have no in-domain calibration fit.

Expected before running: Lower confidence may improve Brier even if the most likely label remains unchanged.

**Iteration 3: market_plus_jev**

Observed issue: Direct and shrunk validation Brier=1.2596044444444445, 0.7716856253550848; business interpretation does not itself learn this return target.

Expected before running: If text carries incremental information, the paired model should beat market-only validation Brier; otherwise reject added complexity.

**Iteration 4: market_plus_jev_strong**

Observed issue: Text-model training Brier=0.4294139013278966, validation Brier=0.6697973282771632, using only 75 training cases. Additional features risk unstable fitting.

Expected before running: Stronger shrinkage may reduce variance; no guarantee of validation improvement.

## One final evaluation

Only predeclared baselines, the selected Jev strategy, and its matched no-Jev ablation were evaluated. Losing candidates were not run on the final set. No configuration changed after this result.

| Method | Brier | Accuracy | Balanced accuracy | Forecast coverage | Label coverage |
|---|---:|---:|---:|---:|---:|
| always_up | 1.1333 | 43.3% | 33.3% | 100.0% | 100.0% |
| always_flat | 1.7333 | 13.3% | 33.3% | 100.0% | 100.0% |
| always_down | 1.1333 | 43.3% | 33.3% | 100.0% | 100.0% |
| training_prior | 0.6795 | 43.3% | 33.3% | 100.0% | 100.0% |
| market_only | 0.7337 | 40.0% | 30.8% | 100.0% | 100.0% |
| legacy | 1.3850 | 20.0% | 38.5% | 100.0% | 100.0% |
| market_plus_jev_strong | 0.6648 | 43.3% | 33.3% | 100.0% | 100.0% |
| market_only_strong | 0.6852 | 43.3% | 33.3% | 100.0% | 100.0% |

### Confusion matrices and abstention

Matrices below use actual rows and predicted columns in up/flat/down order.

**always_up:** [[13, 0, 0], [4, 0, 0], [13, 0, 0]]. Abstention-policy coverage 100.0%, conditional accuracy 43.3%.

**always_flat:** [[0, 13, 0], [0, 4, 0], [0, 13, 0]]. Abstention-policy coverage 100.0%, conditional accuracy 13.3%.

**always_down:** [[0, 0, 13], [0, 0, 4], [0, 0, 13]]. Abstention-policy coverage 100.0%, conditional accuracy 43.3%.

**training_prior:** [[13, 0, 0], [4, 0, 0], [13, 0, 0]]. Abstention-policy coverage 100.0%, conditional accuracy 43.3%.

**market_only:** [[12, 0, 1], [3, 0, 1], [13, 0, 0]]. Abstention-policy coverage 50.0%, conditional accuracy 53.3%.

**legacy:** [[2, 10, 1], [0, 4, 0], [4, 9, 0]]. Abstention-policy coverage 100.0%, conditional accuracy 20.0%.

**market_plus_jev_strong:** [[13, 0, 0], [4, 0, 0], [13, 0, 0]]. Abstention-policy coverage 46.7%, conditional accuracy 57.1%.

**market_only_strong:** [[13, 0, 0], [4, 0, 0], [13, 0, 0]]. Abstention-policy coverage 53.3%, conditional accuracy 50.0%.

## Important final failure cases

| Case | Source title | Actual return | Prediction | Brier |
|---|---|---:|---|---:|
| META-2025-10-01-61ad776118 | Improving Your Recommendations on Our Apps With AI at Meta | -0.7% | up | 1.1638 |
| MSFT-2025-11-18-79b9b8ac4a | From idea to deployment: The complete lifecycle of AI on display at Ignite 2025 | -2.7% | up | 1.1567 |
| AMD-2025-09-15-fb1df6fe96 | Earth During a Powerful Solar Storm | -1.0% | up | 1.1521 |
| NVDA-2025-11-18-02cff6780d | Powering AI Superfactories, NVIDIA and Microsoft Integrate Latest Technologies for Inference, Cybersecurity, Physical AI | -3.8% | up | 1.1242 |
| AMD-2025-11-18-821a2b4b01 | AMD and Eviden to Power Europe’s New Exascale Supercomputer, the First Based in France | -10.5% | up | 1.1106 |
| AAPL-2025-12-09-3059459b7f | Hit Apple Arcade game Sneaky Sasquatch comes to hundreds of Apple Store locations this holiday season | -1.1% | up | 1.0904 |

These are error descriptions after the frozen final evaluation, not prompts for another tuning round. Individual cases and probabilities are in records/final/*.json.

## Uncertainty in the final comparison

A descriptive bootstrap resamples whole calendar months, preserving same-month cross-company co-movement better than treating every article as independent. There are very few month blocks, so these intervals remain exploratory.

Selected minus market_only_strong: mean Brier difference -0.0204, descriptive 95% interval [-0.0484, 0.0149], 30 paired cases across 6 months. Negative favors the selected Jev strategy.

Selected minus training_prior: mean Brier difference -0.0147, descriptive 95% interval [-0.0367, 0.0098], 30 paired cases across 6 months. Negative favors the selected Jev strategy.

## API execution and remaining uncertainty

Pinned model: jev-1.13.0. 887 HTTP attempts across 876 unique cached requests; 11 rejected/error attempts preserved. Reported input tokens: 2,515,391. Estimated token charge at the checked $0.042/million input-token rate: $0.1056; actual account billing was not queried and unmetered failures may add cost.

Feature-reading revenue judgments over the cases that used that strategy: {'favorable': 69, 'mixed': 4, 'unknown': 75, 'adverse': 2}. These are model classifications, not human-verified sentiment labels or financial ground truth.

The API validates concrete model identity, complete typed answers, finite values, probability sums within 1e-6, selected options and usage. Up to three identical attempts are allowed only for protocol/transport failures. Rejected raw responses are retained and never normalized. Exact request hashes cache unchanged judgments. Missing Jev features use an explicit missingness indicator with training-only median imputation; feature-call coverage remains visible in the records.

Historical holdouts cannot remove training-data knowledge. Article revisions, source selection, five-issuer concentration, contemporaneous market expectations missing from inputs, overlapping cross-company macro exposures and a small holdout constrain interpretation. No result here establishes trading profitability.

## Reproduce and understand the implementation

Run from the Jev repository root with Python 3.11+ and requirements from requirements.txt. TYPESAFE_API_KEY is read locally through the existing key helper; credentials are never written to request artifacts.

```powershell
python -B -m unittest jev_benchmark_lab.test_lab -v
python -B -m jev_benchmark_lab.lab smoke
python -B -m jev_benchmark_lab.lab collect
python -B -m jev_benchmark_lab.lab freeze
python -B -m jev_benchmark_lab.lab develop
python -B -m jev_benchmark_lab.lab final
python -B -m jev_benchmark_lab.lab report
python -B -m jev_benchmark_lab.lab audit
```

The saved run is immutable: collection/development/final commands refuse to overwrite frozen/completed phases. A future independent replication needs a fresh lab copy and a new benchmark version; do not rerun this final set as an optimization loop. Source caches permit exact replay; re-downloading does not guarantee the same data vintage.

- data.py: discovery, source extraction, conservative grouping, fixed splits, calendars, archived prices and labels.
- strategy.py: strict input allowlist, Jev transport/cache, original staged baseline and atomic features. Signed economic features equal P(favorable)-P(adverse); unknown probability is retained separately.
- evaluate.py: fixed scoring, coverage and abstention policy. No model fitting.
- experiment.py: training-only models, four recorded candidate iterations, frozen selection and one final pass.
- records/experiment_log.json: every candidate, expected behavior, validation result and retention decision.

## Prospective follow-up procedure

Record a new article exactly as observed, its retrieval timestamp, source metadata and company context; set the cutoff no earlier than actual receipt. Before any subsequent outcome exists, run the frozen selected strategy and save input hash, model version, full probabilities and forecast timestamp. Retain all consecutive eligible events, including failures. After five regular sessions, obtain prices and score with this unchanged evaluator. Do not change a forecast after observing returns. Aggregate future results only after a preregistered event count or end date.

## Sources

- [TypeSafe model versions and pricing](https://docs.typesafe.ai/models)
- [TypeSafe typed API contract](https://docs.typesafe.ai/api)
- [yfinance history parameters](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.history.html)
- [Exchange calendars](https://github.com/gerrymanoim/exchange_calendars)
- Individual publisher URLs, raw source snapshots and retrieval timestamps are embedded in data/cases.json.

<!-- post-run-verification -->
## Post-run verification and independence limitation

All 15 offline checks passed. All 150 saved targets and pre-cutoff market feature vectors were recomputed from archived prices. All 876 unique Jev request states were checked for realized outcome keys and model pins. Prediction code, frozen cases and 124 pre-existing project files remained unchanged.

**The selected model predicted up on all 30 final cases.** Its 43.3% accuracy and 33.3% balanced accuracy match the constant-up classifier. The observed gain is in probability scores, not improved directional classification. Both descriptive Brier-difference intervals include zero.

**The independence audit found an exclusion gap:** the legacy-date rule was applied to issuer news but not the preselected astronomy controls. One final NVIDIA control uses a new source article but shares four trading sessions with an earlier NVIDIA case. This weakens the independence of the final holdout. The run should not be presented as a fully clean unseen-outcome validation.

- New case `NVDA-2025-07-15-aeeb92e2d0` overlaps `20_nvda-policy-h20-license-assurance-2025-07-14` on 2025-07-16, 2025-07-17, 2025-07-18, 2025-07-21.

No case was removed, no score or model was retuned, and no second final evaluation was run after finding this issue. A future benchmark must apply legacy-window exclusion to every source, including controls, before freezing. Any stronger conclusion requires genuinely prospective inputs and outcomes.
