# Jev input representation: percentages and summarized prose

<!-- agentic-run-status:start -->
**Final status:** This is a development follow-up to the unsuccessful pure agentic prompt/question-strategy optimization run. Percentages with descriptions and percentage-based prose did not improve overall accuracy over the raw JSON staged reference. A later correction translated the numbers into qualitative meanings; it reached 45.0% accuracy and improved probability scoring, but remained below the 54.4% market-only/always-up accuracy on these cases. See [QUALITATIVE_REPORT.md](QUALITATIVE_REPORT.md) and [the consolidated summary](README.md). The original comparisons below remain unchanged.

The user-requested documentation refresh changes explanatory Markdown only. [Documentation change manifest](records/documentation_update_2026-10-19.json).
<!-- agentic-run-status:end -->


Model pinned to jev-1.13.0. One reference and exactly two requested representation variants; no tuning after scores.

## Interpretation

The same 150 cases from the latest run were reused: 120 earlier development cases plus 30 January-June 2026 cases. All outcomes had previously been examined. This is a paired development/regression comparison, not an independent final test. The one original split-window exclusion remains, so 149 price labels are scored. No new prices, article research, statistical model fitting or downstream model selection occurred.

Every arm uses the same two-stage business_then_trade question sequence: six business questions together, then one forecast using those answers. The reference reuses the earlier 120 completed staged records and completes the missing 30. The saved single-call method is an additional comparison, not the paired reference for these transformations.

## Results on the same 150 scheduled cases

| Method | Correct / labeled | Accuracy | Balanced accuracy | Brier (lower better) | Forecast coverage |
|---|---:|---:|---:|---:|---:|
| raw_json | 74/149 | 49.7% | 32.6% | 0.7207 | 100.0% |
| percent_descriptions | 70/149 | 47.0% | 32.5% | 0.7324 | 100.0% |
| summarized_prose | 66/149 | 44.3% | 39.8% | 0.7832 | 100.0% |
| saved_single_call | 81/149 | 54.4% | 34.1% | 0.7349 | 100.0% |
| market_only | 81/149 | 54.4% | 33.3% | 0.5910 | 100.0% |
| training_prior | 81/149 | 54.4% | 33.3% | 0.6007 | 100.0% |
| always_up | 81/149 | 54.4% | 33.3% | 0.9128 | 100.0% |
| always_flat | 25/149 | 16.8% | 33.3% | 1.6644 | 100.0% |
| always_down | 43/149 | 28.9% | 33.3% | 1.4228 | 100.0% |

Missing forecasts count wrong for accuracy and incur maximum Brier 2 for paired deltas. Brier in the table is the mean on covered cases; coverage is shown alongside it.

## Paired changes relative to the raw JSON staged method

**percent_descriptions**: 3 corrected cases, 7 new errors. Accuracy change -2.7 percentage points; Brier change +0.0117. Negative Brier change is better. Month-block bootstrap 95% intervals: accuracy -5.9% to 0.0%; Brier -0.0326 to 0.0603. There are 34 month blocks; shared market dependence and prior development exposure remain.

**summarized_prose**: 16 corrected cases, 24 new errors. Accuracy change -5.4 percentage points; Brier change +0.0625. Negative Brier change is better. Month-block bootstrap 95% intervals: accuracy -13.3% to 2.1%; Brier -0.0120 to 0.1417. There are 34 month blocks; shared market dependence and prior development exposure remain.

percent_descriptions: no higher observed accuracy than the paired raw staged reference; no higher accuracy than the strongest fixed non-Jev baseline. The 70% goal was not reached.

summarized_prose: no higher observed accuracy than the paired raw staged reference; no higher accuracy than the strongest fixed non-Jev baseline. The 70% goal was not reached.

## Results by original period

These are historical group names, not fresh train/validation/test roles for this comparison.

| Arm | Original group | Correct / labeled | Accuracy | Brier | Coverage |
|---|---|---:|---:|---:|---:|
| raw_json | holdout | 12/30 | 40.0% | 0.9131 | 100.0% |
| raw_json | train | 43/74 | 58.1% | 0.6292 | 100.0% |
| raw_json | validation | 19/45 | 42.2% | 0.7427 | 100.0% |
| percent_descriptions | holdout | 11/30 | 36.7% | 0.8785 | 100.0% |
| percent_descriptions | train | 40/74 | 54.1% | 0.6478 | 100.0% |
| percent_descriptions | validation | 19/45 | 42.2% | 0.7741 | 100.0% |
| summarized_prose | holdout | 11/30 | 36.7% | 0.8499 | 100.0% |
| summarized_prose | train | 34/74 | 45.9% | 0.7294 | 100.0% |
| summarized_prose | validation | 21/45 | 46.7% | 0.8272 | 100.0% |

## Did the earlier business answers change?

| Arm | Business stages | Revenue choices | Cash choices | Surprise choices | Issuer relevance >=50% | Controls relevance >=50% |
|---|---:|---|---|---|---:|---:|
| raw_json | 150 | {'unknown': 147, 'positive': 3} | {'unknown': 149, 'negative': 1} | {'unknown': 150} | 5/135 | 0/15 |
| percent_descriptions | 150 | {'unknown': 150} | {'unknown': 149, 'negative': 1} | {'unknown': 150} | 3/135 | 0/15 |
| summarized_prose | 150 | {'unknown': 150} | {'unknown': 150} | {'unknown': 150} | 3/135 | 0/15 |

These are behavior distributions, not an adjudicated overall semantic-accuracy score. Missing analyst consensus supports unknown surprise. Unrelated NASA controls should not establish target revenue/cash effects. Direct issuer relevance is a useful sanity screen; it is not a substitute for reviewing every business judgment.

## What exactly changed

- raw_json: original full source excerpts, long decimal market values and prior answers in nested JSON.
- percent_descriptions: same passages and structure, returns/volatility shown to two percentage decimals, probabilities to four percentage decimals, short descriptions and explicit units; equivalent target thresholds in the question expressed as percentages. Absolute currency amounts, counts and publication dates are preserved.
- summarized_prose: a natural-language state with an incomplete source-sentence summary, the company/cutoff/target, all ten pre-cutoff market observations and reference probabilities, followed by attributed natural-language earlier judgments. All alternatives and confidence are preserved as percentages. Unknown is explicitly not no effect or flat.

The prose arm bundles summarization, state shortening, percentage representation, code-computed trend wording and formatting. It cannot establish that JSON punctuation alone caused any change. The source summary uses actual selected source sentences, not a generative rewrite: this avoids introducing fabricated facts but can omit important qualifications or numbers. Every selected sentence and omitted numerical token is saved in data/representation_summaries.json. API transport and returned answers remain JSON; the prose state itself is a plain string.

No summary saw an outcome, correctness flag, future return or exit price. Simple descriptions such as rose/fell/outperformed were calculated from already-saved pre-cutoff values. Historical source-version uncertainty and missing expectations remain explicit. Earlier Jev judgments remain uncertain model judgments, never asserted as established financial facts.

## Input lengths

| Arm | Mean stage-1 input tokens | Mean stage-2 input tokens |
|---|---:|---:|
| raw_json | 4063 | 4780 |
| percent_descriptions | 4229 | 5217 |
| summarized_prose | 2648 | 1977 |

Token lengths are reported from accepted API responses; this experiment changes both length and representation, so it is not a pure context-length intervention.

## Full paired example and errors

The previously discussed Apple News+ Food case: actual down, raw return -1.2616%. Full inputs and outputs for every arm/stage are in [the paired trace](representation_example_AAPL-2025-02-21-216bbb1456_full_trace.md).

- raw_json: {'up': 0.9, 'flat': 0.09, 'down': 0.01}.
- percent_descriptions: {'up': 0.81, 'flat': 0.18, 'down': 0.01}.
- summarized_prose: {'up': 0.73, 'flat': 0.25, 'down': 0.02}.

Confident wrong forecasts (up to three per arm):

- raw_json, NVDA-2023-08-23-29a64831da: predicted up, actual down; probabilities {'up': 0.95, 'flat': 0.04, 'down': 0.01}.
- raw_json, AMD-2024-09-26-3323ae4e96: predicted up, actual down; probabilities {'up': 0.94, 'flat': 0.05, 'down': 0.01}.
- raw_json, NVDA-2024-10-23-bbc88f6fc2: predicted up, actual down; probabilities {'up': 0.93, 'flat': 0.06, 'down': 0.01}.
- percent_descriptions, AMD-2024-09-26-3323ae4e96: predicted up, actual down; probabilities {'up': 0.9, 'flat': 0.09, 'down': 0.01}.
- percent_descriptions, META-2023-07-17-a2a30248e2: predicted up, actual down; probabilities {'up': 0.89, 'flat': 0.1, 'down': 0.01}.
- percent_descriptions, NVDA-2023-08-23-29a64831da: predicted up, actual down; probabilities {'up': 0.9, 'flat': 0.08, 'down': 0.02}.
- summarized_prose, AMD-2025-04-08-944eac180c: predicted down, actual up; probabilities {'up': 0.03, 'flat': 0.06, 'down': 0.91}.
- summarized_prose, AMD-2024-09-26-3323ae4e96: predicted up, actual down; probabilities {'up': 0.88, 'flat': 0.11, 'down': 0.01}.
- summarized_prose, MSFT-2024-10-31-2e9f772eed: predicted down, actual up; probabilities {'up': 0.03, 'flat': 0.08, 'down': 0.89}.

## Coverage, failures and checks

900 unique cached API requests, of which 240 were reused from the preceding run. Saved records contain 25 rejected attempts and 0 exhausted requests. All attempts remain, including failures. 5128 earlier files were hash-checked with zero changes. Replaying the evaluator reproduced the scores. The frozen protocol/input/code manifest is in frozen/representation_inputs.json; environment versions are recorded.

Response/schema validation and identical-request retry rules were frozen before calls. There was no retry based on correctness, no case replacement, and no post-score prompt or summary optimization. Response coverage is valid forecast count / scheduled cases; label coverage separately tracks usable prices. Full-coverage accuracy counts missing forecasts wrong. Confusion matrices, per-case scores and separate max-probability>=0.60 selective coverage/accuracy are in records/representation_scores.json.

## Reproduction

Run from the repository root:

```powershell
python -B jev_benchmark_lab/question_search_10/representation_run.pyw test
python -B jev_benchmark_lab/question_search_10/representation_run.pyw verify
python -B jev_benchmark_lab/question_search_10/representation_run.pyw report
```

A new run follows prepare -> test -> smoke -> run -> report. This completed run refuses another prediction round after scores.json exists; verification and report reproduction use saved results without API calls. Modify a copied experiment folder and freeze a new version for a later comparison.

Main functions: render.numeric_state converts only known ratios/probabilities into described percentages; render.source_summary selects source sentences with saved provenance; render.prose_state assembles natural language and summarizes prior answers; lab.one_case runs the two calls; lab.score reuses the unchanged evaluator; report.paired compares the same events. No statistical coefficients or Jev weights were trained.
