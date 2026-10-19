# Input representation and qualitative-language follow-ups

These are follow-ups to the unsuccessful agentic prompt/question-strategy search. They test whether clearer inputs help the same Jev model; they do not update its weights. All 150 cases were already examined, so these are paired development comparisons with 149 usable frozen price labels.

## Completed comparisons

- Raw JSON: 49.7% accuracy.
- Percentages with short descriptions: 47.0% accuracy.
- Percentage-based prose: 44.3% accuracy.
- Qualitative interpretations of the numbers and earlier Jev answers: 45.0% accuracy.
- Market-only and always-up baselines: 54.4% accuracy on these same cases.

The qualitative rerun improved Brier to 0.6861 including the failed-forecast penalty (0.6772 on covered cases), compared with 0.7832 for the earlier prose. It did not establish better directional accuracy. [README.md](README.md) contains the consolidated assessment and metric definitions.

Read [REPRESENTATION_REPORT.md](REPRESENTATION_REPORT.md) for the first comparison and [QUALITATIVE_REPORT.md](QUALITATIVE_REPORT.md) for the corrected qualitative-wording test. The first prose renderer primarily reformatted percentages; the corrected version describes their meaning, such as relative strength, historical variability and weak or strong support for an earlier judgment.

## Input handling

Raw sources and outcomes remain separate. Renderers do not receive outcome labels. Currency values, dates and exact target boundaries retain their units. Source summaries use selected source sentences; they are incomplete excerpts, not verified historical full text. Qualitative interpretations preserve unknown and attribute earlier judgments to Jev rather than asserting them as facts. The comparison bundles input interpretation, filtering and loss of numerical precision, so it cannot isolate JSON punctuation alone.

## Offline checks and recorded commands

Run from the repository root:

```powershell
python -B jev_benchmark_lab/question_search_10/representation_run.pyw test
python -B jev_benchmark_lab/question_search_10/qualitative_run.pyw test
```

For an unstarted version, each runner follows `prepare`, `test`, `smoke`, `run`, `report`, then `verify`. The recorded runs are complete; do not reset their frozen manifests or treat these cases as a new holdout. Report regeneration reproduces saved metric tables but may overwrite later editorial notes.

## Storage and traces

Everything remains in the existing `question_search_10/` folder tree. `representation_` and `qualitative_` prefixes distinguish inputs, frozen manifests, per-case records and API attempts in the existing directories. Source code for the first comparison is in `representation_code.zip`; the corrected renderer and runner are in `qualitative_run.pyw`.

- [Full first-comparison Apple trace](representation_example_AAPL-2025-02-21-216bbb1456_full_trace.md).
- [Full corrected qualitative Apple trace](qualitative_example_apple_full_trace.md).

## Documentation refresh

Documentation updated after the completed runs. The user requested this status refresh. Saved verification records describe the pre-edit snapshots; preservation checks may flag these named Markdown edits. The before/after hashes are recorded in [the documentation-change manifest](records/documentation_update_2026-10-19.json). Experiment code, frozen manifests, inputs, prices, API responses and scores were not changed. Regenerating an older report can overwrite its later editorial status note.
