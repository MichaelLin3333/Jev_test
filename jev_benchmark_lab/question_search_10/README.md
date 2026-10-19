# Jev agentic prompt and question-strategy optimization

**This pure agentic experiment failed to meet its prediction objective.** It aimed to improve Jev's forecasts by changing prompts, question phrasing, stages, decision rules and input representations. The agent ran a feedback-and-selection loop similar to reinforcement learning: propose a strategy, evaluate it, inspect errors, and retain or reject it. Jev's weights were never updated; the loop optimized the surrounding strategy. Small downstream statistical models were tested separately.

The target was at least 70% accuracy for the fixed five-session up/flat/down return forecast. Neither the ten-iteration search nor the later presentation experiments reached it or demonstrated reliable accuracy gains beyond the baselines. Some probability scores improved; that does not establish a useful directional prediction signal.

## Ten-iteration search

Exactly ten candidates tested direct forecasts, business-to-return stages, continuation/reversal gates, bull/bear questions, simple statistical combinations, cumulative probability questions, alternate wording and ensembles. The best validation accuracy was **53.3% (24/45)**. The selected direct method then scored **40.0% (12/30)** on the fresh historical holdout, tying always-up and predicting up on every case.

Read [REPORT.md](REPORT.md) for every iteration, its before-run expectation and its recorded result. The final holdout was used only after selection; there was no further tuning against that result within the ten-iteration search.

## Follow-up input comparisons

These tests used the same latest 150 cases: 120 earlier development inputs plus 30 newer historical inputs. The one original unscorable price window remains, leaving 149 labels. By this point the outcomes had been examined, so all follow-ups are paired development/regression comparisons, not independent final evaluations.

| Version | Correct / labeled | Accuracy | Balanced accuracy | Brier, including failures | Forecast coverage |
|---|---:|---:|---:|---:|---:|
| Raw JSON, two stages | 74/149 | 49.7% | 32.6% | 0.7207 | 100.0% |
| Percentages with descriptions | 70/149 | 47.0% | 32.5% | 0.7324 | 100.0% |
| Percentage-based prose | 66/149 | 44.3% | 39.8% | 0.7832 | 100.0% |
| Qualitative interpretations | 67/149 | 45.0% | 36.7% | 0.6861 | 99.3% |
| Market-only baseline | 81/149 | 54.4% | 33.3% | 0.5910 | 100.0% |
| Always-up baseline | 81/149 | 54.4% | 33.3% | 0.9128 | 100.0% |

Lower Brier is better. The table charges the maximum Brier of 2 for a missing forecast. The qualitative run had one exhausted response-validation case: its covered-case Brier was 0.6772, while the comparable failure-penalized score above is 0.6861. Missing forecasts count wrong for accuracy.

- [REPRESENTATION_REPORT.md](REPRESENTATION_REPORT.md): raw JSON versus percentage descriptions and percentage-based prose. Prose reduced up bias and improved balanced accuracy, but lowered overall accuracy.
- [QUALITATIVE_REPORT.md](QUALITATIVE_REPORT.md): actual qualitative meanings such as "substantial outperformance" and "weak evidence," instead of percentages written in sentences. It improved probability scoring over the earlier prose but barely changed accuracy.
- [representation_README.md](representation_README.md): commands and storage layout for both follow-ups.
- [First paired trace](representation_example_AAPL-2025-02-21-216bbb1456_full_trace.md): complete original inputs and outputs for raw JSON and the first two representations.
- [Corrected qualitative trace](qualitative_example_apple_full_trace.md): complete before/after inputs and outputs for the qualitative-wording rerun.

## What failed and what remains uncertain

The intermediate business judgments often defaulted to unknown; qualitative wording did not remove that behavior. Missing analyst expectations can justify unknown surprise, but issuer relevance also remained weak. No independently adjudicated overall semantic-accuracy percentage was established.

The original single-call winner defaulted to up on the fresh holdout. Summarization and qualitative interpretations reduced concentrated predictions without establishing an accuracy edge. The current evidence therefore supports an unsuccessful optimization attempt, not a validated forecasting system.

Historical text versions are unverified, model training may already contain historical information, datasets are small and technology-heavy, and repeated validation/development comparisons can overfit. These results do not prove that every prompt strategy or every Jev use case must fail.

## Recorded implementation and replay

`protocol.json`, `questions.py` and `search.py` record the ten-iteration design and question strategies. `representation_protocol.json` and `qualitative_protocol.json` fix the two follow-up designs. Frozen hashes, every accepted/rejected API attempt, outcomes and per-case scores remain saved. Outcome labels and post-cutoff prices were outside model requests.

From the repository root, the offline presentation checks are:

```powershell
python -B -m jev_benchmark_lab.question_search_10.run test
python -B jev_benchmark_lab/question_search_10/representation_run.pyw test
python -B jev_benchmark_lab/question_search_10/qualitative_run.pyw test
```

The completed prediction phases are closed: they refuse an eleventh search iteration or another completed final evaluation. Follow-up renderers are recorded in `representation_code.zip` and `qualitative_run.pyw`. All follow-up files remain alongside the existing folder tree with distinct prefixes.

## Documentation refresh

Documentation updated October 19, 2026, after the completed runs. The user requested this status refresh. Saved verification records describe the pre-edit snapshots; preservation checks may flag these named Markdown edits. The before/after hashes are recorded in [the documentation-change manifest](records/documentation_update_2026-10-19.json). Experiment code, frozen manifests, inputs, prices, API responses and scores were not changed. Regenerating an older report can overwrite its later editorial status note.
