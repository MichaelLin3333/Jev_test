# Jev qualitative-meaning rerun

<!-- agentic-run-status:start -->
**Final status:** Qualitative explanations improved probability scoring but did not rescue prediction accuracy. The result was 45.0% accuracy versus the market-only/always-up baseline's 54.4%. Covered-case Brier below is 0.6772; including the maximum penalty for one failed forecast gives 0.6861. This remains an unsuccessful follow-up to the agentic, RL-like prompt/question-strategy optimization run, with Jev's weights unchanged. See [README.md](README.md) for the overall purpose and outcome. The original result tables and paired comparisons remain unchanged.

The user-requested documentation refresh changes explanatory Markdown only. [Documentation change manifest](records/documentation_update_2026-10-19.json).
<!-- agentic-run-status:end -->


Pinned jev-1.13.0. Same 150 scheduled cases; 149 usable frozen price labels. All cases were already examined, so this is a paired development comparison.

## What changed

The earlier prose renderer spelled out percentages. This rerun interprets their meaning instead: historical movement becomes very small/modest/substantial/strong rises or declines, relative returns become outperformance/underperformance, volatility becomes a variability description, and earlier Jev probabilities become attributed judgments such as weak support or strong evidence of an information gap. Source passages and question sequence are otherwise the same as the preceding prose arm.

Market and prior-answer numbers are absent from the qualitative state. Source dates, currency amounts, source financial rates and exact +/-1% target boundaries remain literal. Where the excerpt explicitly identifies revenue growth or gross/operating/net margin, an additional sentence explains the qualitative financial meaning. An amount without a comparable baseline is not labeled material.

The rendering categories were fixed before calls in qualitative_protocol.json. Movement strength uses a code-computed historical variability scale; it does not estimate statistical significance or future direction. Relative performance uses a simple covariance-free display scale, not a verified alpha estimate. Unknown is insufficient evidence, never no effect. Earlier Jev assessments and reference-model forecasts are always attributed rather than asserted as facts.

No Jev weights or statistical models were fitted. No new sources/prices/outcomes were acquired. Only one qualitative wording configuration was run; no post-score revisions.

## Results

| Method | Correct / labeled | Accuracy | Balanced accuracy | Brier (lower better) | Forecast coverage |
|---|---:|---:|---:|---:|---:|
| raw_json | 74/149 | 49.7% | 32.6% | 0.7207 | 100.0% |
| percent_descriptions | 70/149 | 47.0% | 32.5% | 0.7324 | 100.0% |
| summarized_prose | 66/149 | 44.3% | 39.8% | 0.7832 | 100.0% |
| market_only | 81/149 | 54.4% | 33.3% | 0.5910 | 100.0% |
| always_up | 81/149 | 54.4% | 33.3% | 0.9128 | 100.0% |
| qualitative_meaning | 67/149 | 45.0% | 36.7% | 0.6772 | 99.3% |

## Paired changes

Against raw_json: 13 corrected cases and 20 new errors. Accuracy change -4.7 percentage points; Brier change -0.0346. Paired month-block bootstrap intervals: accuracy -12.8% to 2.9%; Brier -0.0944 to 0.0295.

Against summarized_prose: 15 corrected cases and 14 new errors. Accuracy change +0.7 percentage points; Brier change -0.0971. Paired month-block bootstrap intervals: accuracy -5.1% to 6.2%; Brier -0.1542 to -0.0451.

## Intermediate answers

```json
{
  "revenue": {
    "unknown": 149
  },
  "cash": {
    "unknown": 149
  },
  "surprise": {
    "unknown": 149
  },
  "issuer": {
    "n": 134,
    "relevance_yes_at_least_half": 4,
    "mean": 0.24597014925373129
  },
  "unrelated_controls": {
    "n": 15,
    "relevance_yes_at_least_half": 0,
    "mean": 0.068
  }
}
```

These are behavior distributions, not independently adjudicated semantic accuracy. Unknown surprise can be appropriate because consensus was absent. Direct issuer relevance and unrelated NASA articles are sanity screens, not complete economic ground truth.

## Original chronological groups

These groups are all development comparisons now.

| Original group | Correct / labeled | Accuracy | Balanced accuracy | Brier |
|---|---:|---:|---:|---:|
| holdout | 13/30 | 43.3% | 38.3% | 0.7766 |
| train | 33/74 | 44.6% | 36.6% | 0.6199 |
| validation | 21/45 | 46.7% | 40.0% | 0.7039 |

## Example and input sizes

Apple News+ Food: earlier percentage prose {'up': 0.73, 'flat': 0.25, 'down': 0.02}; new qualitative interpretation {'up': 0.61, 'flat': 0.34, 'down': 0.05}. Actual raw return was down. [Complete paired inputs and outputs](qualitative_example_apple_full_trace.md).

Mean accepted input tokens: business stage 2650; forecast stage 1888. Numerical output probabilities are preserved for scoring.

## Coverage, limitations and verification

299 unique requests, 311 attempts, 13 rejected attempts and 1 exhausted requests. All attempts are saved. 6748 earlier files were hash-checked with zero changes. Scores replayed from the same saved outcomes.

This intervention combines qualitative binning, explanatory wording and some loss of numerical precision. It cannot isolate a pure formatting effect or establish why Jev changed an answer. The same primary-source excerpts and their uncertain historical versions remain a limitation. Repeated development comparisons cannot establish performance on genuinely unseen future outcomes.

Full metrics, confusion matrices and separate selective coverage/accuracy are in records/qualitative_scores.json. Forecast coverage is valid forecast count / scheduled cases; a missing forecast counts wrong for full-coverage accuracy and receives maximum Brier 2 for paired comparisons. The one original unscorable price window remains excluded without replacement.

## Reproduction

```powershell
python -B jev_benchmark_lab/question_search_10/qualitative_run.pyw test
python -B jev_benchmark_lab/question_search_10/qualitative_run.pyw verify
python -B jev_benchmark_lab/question_search_10/qualitative_run.pyw report
```

For an unstarted version the sequence is prepare -> test -> smoke -> run -> report. Completed scores close this prediction run. The code, input hashes and rendering categories are frozen in frozen/qualitative_inputs.json and qualitative_protocol.json. New qualitative_ files remain in the existing folders; prior representation_ and older experiment records are unchanged.
