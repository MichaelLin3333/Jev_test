# Jev benchmark lab

**Outcome: the agentic optimization run failed to reach its prediction goal or demonstrate reliable added value beyond the baselines.**

This folder contains a pure agentic research run that tries to improve Jev through prompt changes, atomic questions, staged question strategies, decision rules and input representations. The agent proposes a change, evaluates it against fixed cases, uses the feedback to retain or reject it, and tries the next candidate. This is an RL-like feedback-and-selection loop at the strategy level, not reinforcement-learning updates to Jev's weights. Small downstream statistical models were also evaluated separately.

## Latest optimization results

- [question_search_10/README.md](question_search_10/README.md): consolidated purpose, failure assessment and all follow-up comparisons.
- [Ten-iteration report](question_search_10/REPORT.md): best validation accuracy 53.3%; fresh holdout accuracy 40.0%, tying always-up. The 70% target was not reached.
- [Input-representation report](question_search_10/REPRESENTATION_REPORT.md): percentage descriptions and percentage-based prose did not improve overall accuracy.
- [Qualitative-meaning report](question_search_10/QUALITATIVE_REPORT.md): interpretation in words improved probability scoring but reached only 45.0% accuracy on previously examined cases, below the 54.4% market-only/always-up accuracy on that comparison.

The later reruns are development comparisons, not new untouched tests. The original benchmark below and the latest follow-ups have different 150-case memberships; their accuracy figures must not be compared as if they used the same cases.

## Original benchmark archive

Start with **[REPORT.md](REPORT.md)** for the completed run and **[results.csv](results.csv)** for the comparison table. [EXISTING_WORK_REVIEW.md](EXISTING_WORK_REVIEW.md) explains the earlier experiments' limitations. [protocol.json](protocol.json) fixes the selection and scoring rules.

[WALKTHROUGH.md](WALKTHROUGH.md) explains the main functions and every feature. The post-run audit flags one final control window overlapping prior work; no row was removed or retuned.

The experiment asks whether Jev adds useful information about five-session stock direction beyond a market-only model and training class frequencies. It is retrospective research; historical text versions and model-training knowledge remain unresolved.

## Small file map

| File/folder | Purpose |
|---|---|
| `data.py` | Publisher archives → dated cases → grouped chronological splits; actual price-derived labels |
| `strategy.py` | Original staged Jev, single-call Jev, atomic Jev features; strict cache and attempt log |
| `evaluate.py` | Frozen Brier, accuracy, balanced accuracy, confusion matrices, coverage and abstention |
| `experiment.py` | Smoke test, training-only fitting, four candidate iterations and one final evaluation |
| `report.py` | Readable findings, exports and descriptive month-block uncertainty |
| `data/cases.json` | Actual inputs, source URLs, body/excerpt status, historical-version uncertainty and timestamps |
| `data/*outcomes.json` | Calculated labels, separate from Jev inputs; final labels created only after selection |
| `records/api_cache/` | Exact requests, raw successful/rejected responses and failure histories; no credentials |
| `records/experiment_log.json` | Every candidate's proposed change, expectation, result and retention decision |
| `frozen/` | Protocol, dataset membership, evaluator hash, training models and selected configuration |

## Commands

Run from the repository root. Python 3.11+ is required; the recorded environment uses Python 3.13.3. Dependencies are pinned in `requirements.txt`. The existing key helper reads `TYPESAFE_API_KEY` locally.

```powershell
python -B -m unittest jev_benchmark_lab.test_lab -v
python -B -m jev_benchmark_lab.lab smoke
python -B -m jev_benchmark_lab.lab collect
python -B -m jev_benchmark_lab.lab freeze
python -B -m jev_benchmark_lab.lab develop
python -B -m jev_benchmark_lab.lab final
python -B -m jev_benchmark_lab.lab report
python -B -m jev_benchmark_lab.lab audit
python -B -m jev_benchmark_lab.audit.verify_run
```

Frozen phases refuse overwriting. An interrupted phase resumes identical requests from their caches. A completed final evaluation cannot be rerun through the command. Future independent experiments need a new version and an untouched test set.

For a read-only replay of this completed run, use `python -B -m jev_benchmark_lab.audit.verify_run`. It checks the frozen inputs, saved-price labels, market-feature cutoffs and request contents without making API calls or fitting another model. Running `report` then the verification module rebuilds the readable report and its audit note. Essential case, price and outcome files are included by the lab's own ignore rules; raw public HTML snapshots and transient Yahoo cookies stay local.

## Reading the calculation

For probabilities up=0.5, flat=0.3, down=0.2 and an actual up outcome, Brier is `(0.5-1)^2 + (0.3-0)^2 + (0.2-0)^2 = 0.38`. Lower is better. This calculation uses the future price label only in the evaluator.

Market features describe only returns and volatility observed before the decision cutoff. Jev features describe supported economic directions, relevance and evidence: a signed revenue feature is `P(favorable) - P(adverse)`, accompanied by `P(unknown)`. They are not stock-return probabilities. A small regularized logistic model learns their relationship to the target using training cases only. The identical model without Jev features is the direct test of incremental value.

Original scripts and historical experiments are protected by a before/after content-hash audit. All new sources and results live here.

## Documentation refresh

Documentation updated October 19, 2026, after the completed runs. The user requested this status refresh. Saved verification records describe the pre-edit snapshots; preservation checks may flag these named Markdown edits. The before/after hashes are recorded in [the documentation-change manifest](question_search_10/records/documentation_update_2026-10-19.json). Experiment code, frozen manifests, inputs, prices, API responses and scores were not changed. Regenerating an older report can overwrite its later editorial status note.
