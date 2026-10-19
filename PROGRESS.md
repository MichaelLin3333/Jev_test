# Tests and progress

Updated October 19, 2026.

**Jev shows useful news-interpretation behavior in selected cases. The current tests do not demonstrate reliable stock prediction.**

## Completed experiments

The recent experiments reuse 27 selected historical NVIDIA cases across nine news categories.

| Experiment | What changed | Result |
| --- | --- | --- |
| Qualitative news study, Oct 17 | Four stages; forecasts may abstain | 27/27 completed; all forecasts returned insufficient evidence |
| Forced-choice forecasts, Oct 18 | Freeze earlier answers; require up/flat/down | 6/27 correct (22.2%); always-down baseline: 13/27 (48.1%) |
| Market-mechanism experiment, Oct 18 | Add questions about trading flows, liquidity, and positioning; compare with a fresh control | Control and added-stage forecasts both scored 6/27; three predictions changed, with one correction and one new error |

The original study distinguished several favorable and adverse business developments. It also exposed category-boundary mistakes and possible unsupported cash-flow assumptions. Good economic interpretation has not translated into better return forecasts here.

## How results were checked

Saved records include inputs, questions, model responses, and attempts. The qualitative study retained five rejected attempts; the market experiment recorded four validation failures before completing all cases.

Return labels use the next session's opening price through the fifth session's closing price, with a ±1% flat band. Later price data were kept outside model requests.

These are exploratory historical tests: one stock, a small selected sample, overlapping windows, missing market expectations, and possible historical knowledge in the model. Known outcomes informed the market experiment's development. Its results are not an independent validation.

## Next steps

1. Resolve the current runner configuration: the forecast's abstention option is commented out, but preflight still requires it. Choose an abstention policy and make the question and validation agree before rerunning.
2. Review classification and cash-flow errors; supply expectations and market context available at the decision time.
3. Test repeatability and evaluate on fresh cases with rules fixed in advance.

## Current code checks

During this cleanup, all three offline previews and the saved-score audit passed. The legacy suite passed 56/64 checks; eight still conflict with the client's newer model setting. The old suite stays local and is excluded from the shared repository.

## Evidence

- [Qualitative findings](jev_model_eval/qualitative_news_tests_2026-10-17/overview.json)
- [Forced-choice scores](jev_model_eval/forced_choice_forecasts_2026-10-18/evaluation.json)
- [Market experiment comparison](jev_model_eval/experimental_market_mechanism_addon_2026-10-18/summary.json)
