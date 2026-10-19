# Jev model evaluation

Experiments with Jev: interpret company news, assess economic effects, and test whether those judgments help forecast stock direction.

**The focus is `jev_model_eval/`. `jev_news/` supplies reusable utilities.** The current historical experiments do not demonstrate reliable stock prediction.

## Start here

| Location | Purpose |
| --- | --- |
| [jev_model_eval/](jev_model_eval/README.md) | Staged evaluations, experimental prompts, and saved results |
| [jev_news/](jev_news/README.md) | Shared API client, news collection, and local archive tools |
| [jev_benchmark_lab/](jev_benchmark_lab/README.md) | Pure agentic, RL-like prompt and question-strategy optimization; the prediction objective was not achieved |
| [PROGRESS.md](PROGRESS.md) | Tests completed, findings, limitations, and next steps |
| [JEV_DEMO.md](JEV_DEMO.md) | Quick walkthrough without live API calls |

## Agentic optimization experiment

[jev_benchmark_lab/](jev_benchmark_lab/README.md), especially [question_search_10/](jev_benchmark_lab/question_search_10/README.md), records a pure agentic research run aimed at improving Jev by modifying prompts, question wording, question stages, decision strategies and input representations. An agent proposed changes, ran the fixed benchmark, inspected evaluation feedback and retained or rejected candidates. This feedback-and-selection loop is similar to reinforcement learning at the prompt/strategy level; Jev's model weights were never updated. Some separate, small statistical models were fitted during the research.

**The experiment failed to meet its objective:** it did not reach 70% prediction accuracy or demonstrate reliable added value beyond simple baselines. The ten-iteration search reached 53.3% validation accuracy, then 40.0% on its fresh 30-case holdout, tying always-up. Later representation and qualitative-language tests reused previously examined cases; some improved probability scoring, but none established an accuracy advantage. See the [experiment summary and final comparisons](jev_benchmark_lab/question_search_10/README.md).

## How it works

News + company context → event → economic effects → magnitude → forecast.

Each stage passes its answers to the next. The forecast can return **insufficient evidence**; a separate experiment forces an up/flat/down choice.

Use Python 3.11+ and run commands from the repository root. The core evaluation scripts use Python's standard library; the benchmark lab records its additional dependencies separately. Reading saved results and previewing requests need no API key; live evaluations use `TYPESAFE_API_KEY`.
