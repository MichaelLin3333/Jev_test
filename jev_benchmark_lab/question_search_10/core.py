"""Reuse the existing validated transport and scoring without editing it."""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone
import numpy as np
from jev_benchmark_lab import common as previous_common
from jev_benchmark_lab import strategy as previous_strategy
from jev_benchmark_lab import data as previous_data
from jev_benchmark_lab import evaluate

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent
REPO = OLD.parent
LABELS = ["up", "flat", "down"]
read = previous_common.read
save = previous_common.save
digest = previous_common.digest
now = previous_common.now

# Redirect helper output folders only in this new process. Existing files and
# the earlier frozen experiment are never edited or executed as a runner.
previous_common.ROOT = ROOT
previous_strategy.ROOT = ROOT
call_jev = previous_strategy.call_jev
fetch = previous_common.fetch

def protocol():
    return read(ROOT / "protocol.json")

def preserve_snapshot():
    files = [p for p in OLD.rglob("*") if p.is_file() and not p.is_relative_to(ROOT) and "__pycache__" not in p.parts and "yfinance_cache" not in p.parts]
    for name in ("jev_news", "jev_model_eval"):
        files += [p for p in (REPO / name).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    return {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}

def verify_previous():
    expected = read(ROOT / "frozen" / "previous_files.json")
    actual = preserve_snapshot()
    changed = [name for name, value in expected.items() if actual.get(name) != value]
    result = {"checked_at": now(), "files_checked": len(expected), "changed": changed, "passed": not changed}
    save(ROOT / "records" / "preservation.json", result)
    if changed:
        raise ValueError("Earlier work changed: " + str(changed))
    return result

def code_hashes():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.glob("*.py")}

def safe_state(case, market, base):
    state = previous_strategy.safe_state(case)
    names = ["stock_return_1", "stock_return_5", "stock_return_20", "stock_volatility_20", "spy_return_1", "spy_return_5", "spy_return_20", "spy_volatility_20", "relative_return_5", "relative_return_20"]
    state["pre_cutoff_market"] = {name: value for name, value in zip(names, market)}
    state["market_context"] = {"status": "observed_before_cutoff", "units": "decimal fractions", "data": state["pre_cutoff_market"]}
    state["base_forecast"] = {"description": "Forecast from an earlier training-only market model; not a realized outcome", "probabilities": base}
    return state

def metrics(ids, predictions, outcomes):
    result = evaluate.score(ids, predictions, outcomes)
    correct = sum(row["correct"] is True for row in result["rows"])
    result["full_coverage_accuracy"] = correct / result["labeled"] if result["labeled"] else 0.0
    result["correct"] = correct
    result["goal_70_reached"] = result["full_coverage_accuracy"] >= 0.70 and result["forecast_coverage"] == 1.0
    return result

def rank(result):
    return (result["full_coverage_accuracy"], result["balanced_accuracy"] or 0.0, -(result["selection_brier_failure_penalized"] if result["selection_brier_failure_penalized"] is not None else 2.0))

def average(distributions):
    if not distributions or any(value is None for value in distributions):
        return None
    return {label: float(np.mean([value[label] for value in distributions])) for label in LABELS}
