# Model evaluation

The main research folder: test how Jev moves from news interpretation to a stock-direction forecast.

## Main scripts

| Script | Purpose |
| --- | --- |
| `run_eval.py` | Editable case, prompts, and four-stage plan: event → economics → magnitude → forecast |
| `run_eval_experimental_market_mechanism_addon.py` | Compare a frozen forecast with one augmented by market-mechanism questions |
| `check_api.py` | Read `TYPESAFE_API_KEY` from the environment, with a Windows user-environment fallback |

Other small scripts are manual API or collection helpers.

## Saved experiments

| Folder | Contents |
| --- | --- |
| `qualitative_news_tests_2026-10-17/` | 27 cases, four-stage responses, qualitative findings, and rejected attempts |
| `forced_choice_forecasts_2026-10-18/` | Forecast-only reruns, archived prices, and return scoring |
| `experimental_market_mechanism_addon_2026-10-18/` | Fresh controls, added market questions, and paired comparisons |

Open each folder's `overview.json` or `summary.json` first; numbered JSON files contain individual cases. Earlier batch results are archived evidence, not a one-command batch runner.

## Running

Start with the [preview walkthrough](../JEV_DEMO.md). For a new case, edit `CASE` or `CASE_FILE` and the settings in `run_eval.py`. Set `OUTPUT_FILE` to a new JSON filename to save a run; otherwise it only prints.

The current main runner's forecast configuration fails preflight: its abstention option is disabled while validation still requires it. The walkthrough previews the first three stages; [PROGRESS.md](../PROGRESS.md) records the blocker.

`run_eval.py` currently enables live calls. The market experiment previews by default and requires `--live` to call the API; `--all-cases` selects all 27 archived cases. That experiment pins `jev-1.13.0`; the main script currently requests `jev-latest`.

See [PROGRESS.md](../PROGRESS.md) for findings and remaining work.
