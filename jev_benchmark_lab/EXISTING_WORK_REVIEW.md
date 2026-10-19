# Existing work reviewed before the new benchmark

Reviewed October 19, 2026; no existing scripts or records were changed.

- The original 27 NVIDIA cases cover nine event categories, but are selected, short historical summaries from a single issuer. Many return windows overlap. There is no independent held-out result.
- The four-stage study completed all cases but abstained on every forecast. This establishes execution, not forecasting skill.
- Removing abstention while freezing earlier judgments produced 6/27 correct (22.2%), below always-up (44.4%) and always-down (48.1%). Its sum-of-three-class Brier score was 1.16324; only 3/10 forecasts with maximum probability at least 0.90 were correct.
- The market-mechanism add-on also scored 6/27. The fresh control changed one archived prediction; the add-on changed three, correcting one and spoiling one. Brier changed from 1.16498 to 1.16104. Known outcomes informed the add-on, so this is development evidence.
- Missing expectations and pre-decision market observations make a business interpretation different from a post-opening return prediction. The target omits the first announcement/overnight reaction and is not a causal news effect or trading profit.
- Some answers confuse primary event types, gross versus operating margins, corporate versus personal spending, accounting charges versus new cash, and total exposure versus incremental change.
- Current run_eval.py omits the abstention choice while requiring it in preflight. The main client requests an alias, whereas the historical records identify jev-1.13.0. The new lab will pin that concrete version without editing either script.
- The early NVIDIA/Meta/Apple pilot establishes basic sign reading on obvious cases; an elementary word rule also matched all three. Prior familiar cases, source URLs and nearby NVIDIA dates will be excluded from new sampling.

The new experiment must freeze its selection and evaluation rules before obtaining new returns, separate chronological development from a final test, use actual prices for labels, retain failed responses, and compare the same statistical predictor with and without Jev features. Historical holdout results still cannot rule out model-training knowledge.

Evidence: ../jev_model_eval/qualitative_news_tests_2026-10-17/overview.json; ../jev_model_eval/forced_choice_forecasts_2026-10-18/evaluation.json; ../jev_model_eval/experimental_market_mechanism_addon_2026-10-18/summary.json.
