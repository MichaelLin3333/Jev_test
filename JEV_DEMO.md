# Quick walkthrough

Run these commands from the repository root with Python 3.11+.

## 1. Preview the first three stages

This overrides the script's live setting for this run; it reads no API key and sends no requests.

```sh
python -B -c "from jev_model_eval import run_eval as r; r.RUN_MODEL = False; r.STOP_AFTER = 'magnitude'; raise SystemExit(r.main())"
```

The output shows the event, economics, and magnitude questions. Earlier-stage answers remain pending in preview mode. The forecast is skipped because its current configuration needs the fix described in [PROGRESS.md](PROGRESS.md).

## 2. Preview the market-mechanism experiment

```sh
python -B -m jev_model_eval.run_eval_experimental_market_mechanism_addon
```

This shows the planned control and added market questions for one archived case.

## 3. Read the findings

See [PROGRESS.md](PROGRESS.md) for the short summary and [jev_model_eval/](jev_model_eval/README.md) for the saved evidence.

Before running live forecasts, resolve that configuration issue and provide `TYPESAFE_API_KEY`. The main script has `RUN_MODEL = True`; the market experiment requires `--live`.
