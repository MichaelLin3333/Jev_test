# Ten iterations of Jev question-strategy optimization

<!-- agentic-run-status:start -->
**Final status:** This report records the ten-iteration portion of a pure agentic, RL-like feedback-and-selection run that optimized prompts and question strategies around fixed Jev weights. It failed to reach the 70% accuracy goal: best validation accuracy was 53.3%, and the selected configuration scored 40.0% on the fresh holdout, tying always-up. Later presentation tests also failed to establish an accuracy advantage. See [the consolidated folder summary](README.md) and [the latest qualitative report](QUALITATIVE_REPORT.md). The closed-run tables below remain unchanged.

The user-requested documentation refresh changes explanatory Markdown only. [Documentation change manifest](records/documentation_update_2026-10-19.json).
<!-- agentic-run-status:end -->


Model pinned to **jev-1.13.0**. Exactly **10** candidate iterations; stopped after iteration 10.

Best validation configuration: **1: market_aware_direct**, 24/45 correct (**53.3%**). Fresh 2026 holdout: 12/30 correct (**40.0%**), balanced accuracy 33.3%, Brier 0.9643, forecast coverage 100.0%.

The 70% full-coverage goal was not reached on validation and not reached on the fresh holdout. The holdout accuracy's approximate 95% Wilson interval is 24.6%–57.7%. This interval assumes independent cases; shared market exposure makes that optimistic.

## What was fixed before the search

The earlier final-test labels were never read by this experiment. Earlier 75 training / 45 validation inputs were reused for development, with 74 valid training labels and one already excluded split-window case. All 30 earlier final cases and original NVIDIA examples were excluded from new tuning and checked for same-stock target-session overlap when selecting fresh cases. Thirty new inputs were frozen before iteration 1: January–June 2026, six per company across NVDA, AAPL, AMD, META and MSFT (five issuer excerpts plus one unrelated NASA control).

This is an accuracy-targeting follow-up: selection maximizes correct/labeled validation cases, treating missing forecasts as incorrect. Ties use balanced accuracy, then lower failure-penalized Brier, then earlier iteration. The earlier benchmark selected by Brier; both probability quality and accuracy are reported here. No target threshold, case membership or outcome was changed to reach 70%.

Entry is the first XNYS regular-session open strictly after the end-of-source-date New York cutoff. Exit is the fifth session close, counting entry as session one. Return is close/open−1: up >+1%, flat inclusive ±1%, down <−1%. Reused frozen exchange_calendars 4.12 labeling logic. Yahoo/yfinance auto_adjust=False, actions=True, repair=False; vendor split-adjusted OHLC excludes cash dividends. Windows containing a split, missing/nonpositive bars, or predeclared split-boundary overlap remain unscored with no replacements after freeze. This predicts subsequent raw returns, not the announcement's initial or causal effect.

Jev sees only input excerpts, company context, and cutoff-safe market observations. Statistical coefficients fit training only. Earlier winning market probabilities are a forecast reference, never a realized label. Per-case outcome labels and exit prices are outside every API request. Adaptive prompt changes use only aggregate validation failure patterns.

## All ten iterations

| # | Branch | Train accuracy | Validation accuracy | Balanced accuracy | Brier ↓ | Coverage | Retained as best |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | market_aware_direct | 60.8% | 53.3% (24/45) | 34.2% | 0.7422 | 100.0% | yes |
| 2 | business_then_trade | 58.1% | 42.2% (19/45) | 28.1% | 0.7427 | 100.0% | no |
| 3 | continuation_reversal_tree | 60.8% | 53.3% (24/45) | 33.3% | 0.6350 | 100.0% | no |
| 4 | bull_bear_adjudication | 55.4% | 46.7% (21/45) | 34.3% | 0.8603 | 97.8% | no |
| 5 | horizon_features_logistic | 67.6% | 44.4% (20/45) | 36.9% | 0.6633 | 100.0% | no |
| 6 | pricing_features_shallow_tree | 59.5% | 44.4% (20/45) | 42.8% | 0.7082 | 100.0% | no |
| 7 | ordered_return_thresholds | 60.8% | 53.3% (24/45) | 33.3% | 0.5678 | 100.0% | no |
| 8 | reverse_wording_ensemble | 60.8% | 46.7% (21/45) | 30.8% | 0.7315 | 100.0% | no |
| 9 | market_regime_question_tree | 59.5% | 46.7% (21/45) | 30.8% | 0.8279 | 100.0% | no |
| 10 | retained_branch_ensemble | 60.8% | 53.3% (24/45) | 33.3% | 0.6193 | 100.0% | no |

Retention is relative to earlier candidates. Every unsuccessful candidate is preserved. Separate branch experiments change architecture; iteration 6 changes both feature wording and learner relative to 5, so that comparison cannot isolate a wording effect. Matched no-Jev comparisons isolate the additional feature bundle within each learner.

## Validation baselines

| Method | Correct | Accuracy | Balanced accuracy | Brier ↓ | Forecast coverage |
|---|---:|---:|---:|---:|---:|
| training_prior | 24/45 | 53.3% | 33.3% | 0.6038 | 100.0% |
| previous_market_only | 24/45 | 53.3% | 33.3% | 0.5929 | 100.0% |
| previous_best_jev | 24/45 | 53.3% | 33.3% | 0.5892 | 100.0% |
| always_up | 24/45 | 53.3% | 33.3% | 0.9333 | 100.0% |
| always_flat | 6/45 | 13.3% | 33.3% | 1.7333 | 100.0% |
| always_down | 15/45 | 33.3% | 33.3% | 1.3333 | 100.0% |

## Fresh holdout: selected once after all tuning

| Method | Correct | Accuracy | Balanced accuracy | Brier ↓ | Forecast coverage |
|---|---:|---:|---:|---:|---:|
| selected | 12/30 | 40.0% | 33.3% | 0.9643 | 100.0% |
| previous_market_only | 12/30 | 40.0% | 33.3% | 0.7420 | 100.0% |
| training_prior | 12/30 | 40.0% | 33.3% | 0.7182 | 100.0% |
| always_up | 12/30 | 40.0% | 33.3% | 1.2000 | 100.0% |
| always_flat | 7/30 | 23.3% | 33.3% | 1.5333 | 100.0% |
| always_down | 11/30 | 36.7% | 33.3% | 1.2667 | 100.0% |
| previous_best_jev | 12/30 | 40.0% | 33.3% | 0.7556 | 100.0% |

Only the selected configuration, its required component branches and the fixed baselines ran on this holdout. Other candidates were not ranked on these outcomes, and no changes followed the result.

### Does Jev add value?

Compared with always_up, accuracy difference is +0.0 percentage points and Brier difference is -0.2357 (negative favors the selected method). Paired six-month block bootstrap 95% intervals: accuracy 0.0% to 0.0%; Brier -0.4038 to -0.1316.

Compared with previous_market_only, accuracy difference is +0.0 percentage points and Brier difference is 0.2223 (negative favors the selected method). Paired six-month block bootstrap 95% intervals: accuracy 0.0% to 0.0%; Brier 0.0449 to 0.4141.

Compared with previous_best_jev, accuracy difference is +0.0 percentage points and Brier difference is 0.2087 (negative favors the selected method). Paired six-month block bootstrap 95% intervals: accuracy 0.0% to 0.0%; Brier 0.0398 to 0.3969.

This search does not demonstrate an accuracy advantage over the strongest fixed comparison. An attractive validation score alone does not establish predictive value.

## Branch proposals and stage graphs

Exact instructions, option definitions, before-run expectations, aggregate feedback, parent selection and timestamps are in records/proposals/01.json through 10.json. questions.py is the editable prompt library. The winning fully resolved proposal is also in frozen/selection.json.

1. Input + pre-cutoff market → direct three-class forecast.
2. Input → six atomic business questions → self-describing answers + original input → return forecast.
3. Input → nine mechanism questions → economic relevance gate → market fallback or continuation/reversal forecast.
4. Input → independent bull/bear evidence → neutral adjudication.
5. Input → 24 horizon features → training-only balanced logistic regression with 10 market features.
6. Input → 24 pricing features → training-only depth-two decision tree; minimum leaf 12.
7. Input → P(return <−1%) and P(return ≤+1%) → deterministic three-class probabilities.
8. Input → reversed-option wording → equal probability average with the best earlier direct branch.
9. Reuse iteration-6 features → unsupported-news market fallback, else bearish / relative-momentum / neutral question selected from pre-cutoff observations.
10. Equal probability average of the three best earlier validation candidates; no tuned weights.

Atomic answers are named and passed forward with their original question and option definitions. Features: seven evidence probabilities; for each revenue/cash/surprise/continuation/margin channel, favorable-minus-adverse, mixed and unknown probabilities; realized-action probability; missing-response indicator (24). Version 1 leaves the absent priced-reaction feature at zero. Logistic C=.05, class_weight=balanced; no parameter grid. The shallow tree uses max_depth=2, min_samples_leaf=12. Both have median imputation and market-only ablations.

For iteration 7, down=lower CDF, flat=upper−lower, up=1−upper. If lower>upper, both CDFs are pooled at their mean and the conflict is recorded. Valid API outputs are never silently renormalized. Equal ensembles require every component, preserving missing coverage. Multiclass Brier is the mean sum of the three squared probability errors (range 0–2); lower is better. Confusion matrices use actual rows and predicted columns. Balanced accuracy is mean class recall. Missing forecasts are incorrect for the 70% goal and incur Brier 2 for selection.

## Errors, abstention and uncertainty

Selected holdout confusion matrix (actual rows, predicted columns):

| Actual \ Predicted | up | flat | down |
|---|---:|---:|---:|
| up | 12 | 0 | 0 |
| flat | 7 | 0 | 0 |
| down | 11 | 0 | 0 |

Separate selective policy, max probability ≥0.60: coverage 86.7%, conditional accuracy 38.5%. This cannot satisfy the full-coverage goal by hiding difficult cases.

Largest confident holdout errors:

- round2-MSFT-2026-03-09-d879ceb99f: Introducing the First Frontier Suite built on Intelligence + Trust. Predicted up, actual down, return -2.5%; probabilities {'up': 0.96, 'flat': 0.04, 'down': 0.0}.
- round2-NVDA-2026-04-29-cb400cb191: NVIDIA Sets Conference Call for First-Quarter Financial Results. Predicted up, actual down, return -1.0%; probabilities {'up': 0.92, 'flat': 0.06, 'down': 0.02}.
- round2-AMD-2026-02-03-65292eba2a: AMD Reports Fourth Quarter and Full Year 2025 Financial Results. Predicted up, actual flat, return -0.7%; probabilities {'up': 0.93, 'flat': 0.03, 'down': 0.04}.
- round2-META-2026-04-27-f4ec16634e: Powering AI, Strengthening the Grid: Innovation in Space Solar Energy and Long-Duration Storage. Predicted up, actual down, return -9.5%; probabilities {'up': 0.89, 'flat': 0.1, 'down': 0.01}.
- round2-META-2026-04-15-cbdd6439aa: The ISS Transits the Moon. Predicted up, actual flat, return -0.2%; probabilities {'up': 0.94, 'flat': 0.06, 'down': 0.0}.
- round2-AAPL-2026-06-08-b85898c01a: Apple previews new child safety features. Predicted up, actual down, return -1.3%; probabilities {'up': 0.87, 'flat': 0.11, 'down': 0.02}.

Repeated optimization on only 45 validation cases can overfit the validation set. The fresh holdout has only 30 scheduled cases and six month blocks. Stocks share macro exposure, issuer language is promotional, and calendar dates do not establish what the market expected. Historical excerpts were downloaded today; first-observed is actual retrieval, and exact historical text versions remain uncertain. Company profiles are static source descriptions rather than a verified point-in-time fundamentals database. Jev may have memorized historical information despite instructions not to use it. All results are retrospective evidence.

## Coverage and records

Development inputs: 120; valid training labels 74/75 and validation labels 45/45. Fresh inputs: 30; label statuses {'ok': 30}; forecast coverage 100.0%. Source exclusions before freeze: 1 (full reasons in data/source_exclusions.json). No exclusions were introduced after inspecting returns. All 30 fresh articles are publisher excerpts, not proven historical full text. Company counts: {'NVDA': 6, 'AAPL': 6, 'AMD': 6, 'META': 6, 'MSFT': 6}.

API cache: 1322 unique requests, 1362 total attempts, 41 rejected attempts, 1 exhausted requests. Strict response/model/schema validation and identical-request retries (maximum three) were fixed before experiments. All attempts remain in records/api_cache. Original experiment preservation: 2407 existing files checked, zero changed. Dataset, strategy, model and selection hashes are in frozen/; records/verification.json replays final labels and scores and audits request keys.

## Reproduction and modification

Run from the repository root with Python 3.13 and the existing environment:

```powershell
python -B -m jev_benchmark_lab.question_search_10.run test
python -B -m jev_benchmark_lab.question_search_10.run verify
python -B -m jev_benchmark_lab.question_search_10.run report
```

The saved run is closed: iterate refuses after selection and final refuses after its completed result. Cached inputs, raw API responses, probabilities, historical prices and deterministic label replay reproduce these results without new calls. For a separate research run, copy the small source package into a new folder and freeze a new protocol and holdout before prepare → test → iterate → final → report. Do not delete the frozen selection or reuse this holdout for tuning.

Main functions: data_sets.prepare selects and freezes real sources without prices; core.safe_state allowlists request inputs; questions.definitions defines the staged question graphs; search.predict_case executes one case; search.fit fits training-only models; search.iterate records exactly ten development candidates and selects once; search.final applies that frozen choice to fresh cases; reporting.verify recomputes final labels/scores and checks preservation. The fixed scorer remains ../evaluate.py.

## Prospective procedure

Choose future companies/dates and sampling rules in a new protocol first. At each cutoff save the actual article text, source and first-observed timestamp, point-in-time company context and market observations; run the frozen winning questions/model; write a timestamped, hashed forecast before the entry open. Keep the forecast immutable (for example a dated Git commit or append-only external receipt). After the fifth session close acquire prices and label using the same function. Evaluate at the predeclared sample size without choosing a new strategy from interim outcomes. Treat any later prompt change as a new version with a new untouched evaluation period.
