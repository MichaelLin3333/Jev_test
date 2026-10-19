# Jev model evaluation

Experiments with Jev: interpret company news, assess economic effects, and test whether those judgments help forecast stock direction.

**The focus is `jev_model_eval/`. `jev_news/` supplies reusable utilities.** The current historical experiments do not demonstrate reliable stock prediction.

## Start here

| Location | Purpose |
| --- | --- |
| [jev_model_eval/](jev_model_eval/README.md) | Staged evaluations, experimental prompts, and saved results |
| [jev_news/](jev_news/README.md) | Shared API client, news collection, and local archive tools |
| [PROGRESS.md](PROGRESS.md) | Tests completed, findings, limitations, and next steps |
| [JEV_DEMO.md](JEV_DEMO.md) | Quick walkthrough without live API calls |

## How it works

News + company context → event → economic effects → magnitude → forecast.

Each stage passes its answers to the next. The forecast can return **insufficient evidence**; a separate experiment forces an up/flat/down choice.

Use Python 3.11+ and run commands from the repository root. The evaluation scripts use Python's standard library. Reading saved results and previewing requests need no API key; live evaluations use `TYPESAFE_API_KEY`.
