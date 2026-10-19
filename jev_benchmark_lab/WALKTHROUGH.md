# How to understand this experiment

<!-- agentic-run-status:start -->
This walkthrough explains the initial benchmark's implementation. For the purpose and unsuccessful outcome of the later pure agentic, RL-like prompt/question-strategy optimization loop, read [question_search_10/README.md](question_search_10/README.md). The loop used evaluation feedback to select strategies; Jev's weights were not trained.
<!-- agentic-run-status:end -->

The final result is a small probability-score improvement with substantial uncertainty. It is not a demonstrated directional edge: the selected model predicted up on all 30 final cases, matching the constant-up classifier's 43.3% accuracy. A post-run audit also found one control window overlapping prior work. Read the final audit section in REPORT.md before interpreting the result.

## Data moves through ordinary JSON objects

1. `data.archive_rows()` reads a publisher's dated article list. `article_text()` downloads one selected item and extracts actual source passages. It records the URL, body selector, content hash and today's observation time; it never invents a historical retrieval time.
2. `data.collect()` groups nearby releases, reserves the fixed news categories and selects dates without looking at returns. It writes `data/cases.json`. That file is the JSON input to the rest of the experiment.
3. `data.target_window()` uses the XNYS exchange calendar to choose the first executable opening and fifth session's close. Holidays and early closes come from the calendar, not a weekday shortcut.
4. `data.freeze()` locks the case IDs, groups, splits and evaluator/data-code hashes. No failed case can be replaced after this step.
5. `data.label_case()` computes `exit_close / entry_open - 1` from archived prices. Decimal comparison makes the ±1% boundaries inclusive. A split inside the window or missing target bars produces an explicit unscored status. Label files stay separate from Jev inputs.

## What goes into Jev

`strategy.safe_state()` builds an explicit allowlist of company description, source article, cutoff, assumptions and target definition. A label or future price accidentally added elsewhere in a case is not forwarded.

`strategy.call_jev()` hashes the exact request, returns a validated cached answer when available, and otherwise calls the pinned model. Every raw response and rejected attempt is saved. It does not know the correct price outcome, so it cannot retry because an answer is wrong.

`strategy.run_case()` has three text strategies:

- `legacy`: the existing event/economics/magnitude questions, then a forced up/flat/down forecast.
- `single_direct`: the same final forecast question without the earlier stages.
- `features`: atomic economic and evidence questions, without asking Jev for a stock forecast.

## The statistical model's inputs

There are ten market features: stock and SPY 1-, 5- and 20-session returns, their 20-session daily volatility, and stock-minus-SPY 5- and 20-session returns. `data.market_features()` uses only session closes available by the case cutoff.

There are fourteen Jev features:

| Feature | Meaning |
|---|---|
| `economic_event` | Support for a substantive economic event |
| `relevance` | Support for a specific connection to the target company |
| `increment_supported` | Support for a numerical incremental change against a comparable baseline |
| `revenue_signed`, `revenue_unknown` | Revenue P(favorable) − P(adverse), plus P(unknown) |
| `margin_signed`, `margin_unknown` | Operating-margin direction and uncertainty |
| `cash_signed`, `cash_unknown` | Investment/working-capital cash-flow direction and uncertainty |
| `discount_signed`, `discount_unknown` | Required-return/valuation-support direction and uncertainty |
| `surprise_signed`, `surprise_unknown` | Direction against explicitly supplied expectations and uncertainty |
| `jev_missing` | One if feature extraction failed; zero otherwise |

These are economic classifications, not stock probabilities. `experiment.fit_model()` learns a small logistic model connecting them to price labels. It fits imputation, scaling and coefficients on the 74 labeled training cases only. It never learns from validation or final labels.

The matched comparison uses the same fitting procedure and regularization, with or without the fourteen Jev features. `C=0.01` means stronger regularization than `C=0.1`; it discourages large fitted coefficients in this small dataset.

## Why Brier can improve while accuracy stays unchanged

For an actual up outcome and predicted probabilities `(up=.5, flat=.3, down=.2)`, Brier is `.25 + .09 + .04 = .38`. Lower is better. This is an illustrative calculation, not an additional experiment.

Accuracy uses only the largest probability. Changing a distribution from strongly up to mildly up can improve Brier on an actual down outcome, while the selected label remains up and still counts as incorrect. That distinction explains why the selected model's final Brier improved while its directional accuracy did not.

`evaluate.score()` also reports confusion matrices, balanced accuracy, coverage and a separate abstention policy. Flat always means a return within ±1%; it never means the system lacks evidence. The policy accepts only forecasts whose maximum probability reaches 0.60 and reports conditional accuracy alongside its coverage.

## Where the improvement loop stops

`experiment.develop()` records four proposals and validation results. It selects and saves the strongest Jev configuration and training-fitted models. `experiment.final()` checks those hashes and performs one final evaluation. It refuses a second completed run.

The post-run audit does not remove the overlapping control or recompute a more favorable score. It records the defect and limits the conclusion. A future independent run should fix that exclusion for all sources before freezing a new dataset; this final set must not become another tuning set masquerading as an untouched test.
