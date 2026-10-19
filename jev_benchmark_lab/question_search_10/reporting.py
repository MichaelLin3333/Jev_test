"""Readable results and a replay audit; no strategy changes or fresh forecasts."""
from collections import Counter
from pathlib import Path
import csv
import hashlib
import math
from statistics import NormalDist
import numpy as np
from .core import ROOT, OLD, LABELS, read, save, now, digest, metrics, code_hashes, verify_previous, previous_data, previous_strategy
from .data_sets import verify_dataset


def status():
    completed = sorted((ROOT / "records" / "iterations").glob("*.json"))
    print("Completed iterations:", len(completed))
    for path in completed:
        item = read(path)
        val = item["metrics"]["validation"]
        print(item["iteration"], item["proposal"]["name"], "validation accuracy", val["full_coverage_accuracy"], "Brier", val["brier"])
    print("Holdout labels exist:", (ROOT / "data" / "holdout_outcomes.json").exists())


def wilson(correct, n):
    if not n:
        return [None, None]
    z = NormalDist().inv_cdf(.975)
    p = correct/n
    denominator = 1 + z*z/n
    center = (p + z*z/(2*n))/denominator
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n))/denominator
    return [max(0., center-half), min(1., center+half)]


def paired_month_interval(selected, baseline, cases):
    """Paired month-block bootstrap; approximate with only six month blocks."""
    dates = {case["case_id"]: case["decision_time"][:7] for case in cases}
    other = {row["case_id"]: row for row in baseline["rows"]}
    groups = {}
    for row in selected["rows"]:
        prior = other[row["case_id"]]
        if row["brier"] is None or prior["brier"] is None:
            continue
        groups.setdefault(dates[row["case_id"]], []).append((int(row["correct"])-int(prior["correct"]), row["brier"]-prior["brier"]))
    if not groups:
        return None
    groups = list(groups.values())
    rng = np.random.default_rng(2718)
    draws = []
    for _ in range(5000):
        rows = [row for index in rng.integers(0, len(groups), len(groups)) for row in groups[index]]
        draws.append(np.mean(rows, axis=0))
    intervals = np.quantile(draws, [.025, .975], axis=0)
    return {"blocks": len(groups), "accuracy_difference_95_interval": intervals[:,0].tolist(), "brier_difference_95_interval": intervals[:,1].tolist(), "replicates": 5000, "seed": 2718}


def verify():
    verify_dataset()
    preservation = verify_previous()
    forbidden = {"label", "labels", "outcome", "outcomes", "actual", "future_return", "entry_open", "exit_close"}
    requests = []
    bad_keys = []
    attempts = rejected = failed = 0
    versions = Counter()
    def visit(value, where):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in forbidden:
                    bad_keys.append(where + "." + key)
                visit(child, where + "." + key)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                visit(child, where + "." + str(i))
    for path in (ROOT / "records" / "api_cache").glob("*.json"):
        value = read(path)
        request = value["request"]
        assert digest(request) == path.stem
        visit(request["state"], path.stem)
        requests.append(path.stem)
        attempts += len(value["attempts"])
        rejected += sum(attempt.get("status") == "rejected" for attempt in value["attempts"])
        failed += value["status"] != "ok"
        if value["status"] == "ok":
            previous_strategy.validate(value["response"], request["questions"])
            versions[value["response"]["model"]] += 1
    assert not bad_keys, bad_keys
    iterations = sorted((ROOT / "records" / "iterations").glob("*.json"))
    assert len(iterations) <= 10
    result = {"verified_at": now(), "iterations": len(iterations), "unique_requests": len(requests), "attempts": attempts, "rejected_attempts": rejected, "failed_requests": failed, "response_versions": dict(versions), "outcome_keys_in_requests": bad_keys, "previous_files": preservation}
    if (ROOT / "frozen" / "selection.json").exists():
        selection = read(ROOT / "frozen" / "selection.json")
        assert len(iterations) == selection["iteration_count"] == 10
        assert selection["code_hashes"] == code_hashes()
        assert selection["holdout_labels_seen"] is False
        for name, expected in selection["model_hashes"].items():
            assert hashlib.sha256((ROOT / "frozen" / "models" / name).read_bytes()).hexdigest() == expected
        result["selection_frozen_at"] = selection["selected_at"]
    if (ROOT / "records" / "final.json").exists():
        cases = read(ROOT / "data" / "holdout_cases.json")
        outcomes = read(ROOT / "data" / "holdout_outcomes.json")
        prices = {ticker: read(ROOT / "data" / "holdout_prices" / (ticker + ".json")) for ticker in ("NVDA", "AAPL", "AMD", "META", "MSFT", "SPY")}
        for ticker, value in prices.items():
            assert value["retrieved_at"] > result["selection_frozen_at"], ticker
        for case in cases:
            self_outcome = previous_data.label_case(case, prices[case["company"]["ticker"]]["bars"])
            assert self_outcome == outcomes[case["case_id"]]
        predictions = read(ROOT / "records" / "final_predictions.json")
        final = read(ROOT / "records" / "final.json")
        for name, values in predictions.items():
            replay = metrics([case["case_id"] for case in cases], values, outcomes)
            assert replay == final["results"][name], name
        result["final_score_and_price_label_replay"] = True
    result["passed"] = True
    save(ROOT / "records" / "verification.json", result)
    print("VERIFIED", {key:value for key,value in result.items() if key != "previous_files"}, flush=True)
    return result


def pct(value):
    return "n/a" if value is None else f"{100*value:.1f}%"


def number(value):
    return "n/a" if value is None else f"{value:.4f}"


def metric_table(values):
    lines = ["| Method | Correct | Accuracy | Balanced accuracy | Brier ↓ | Forecast coverage |", "|---|---:|---:|---:|---:|---:|"]
    for name, value in values.items():
        lines.append(f"| {name} | {value['correct']}/{value['labeled']} | {pct(value['full_coverage_accuracy'])} | {pct(value['balanced_accuracy'])} | {number(value['brier'])} | {pct(value['forecast_coverage'])} |")
    return lines


def report():
    audit = verify()
    selection = read(ROOT / "frozen" / "selection.json")
    final = read(ROOT / "records" / "final.json")
    selected = final["results"]["selected"]
    validation = selection["metrics"]
    dev = read(ROOT / "data" / "development_cases.json")
    cases = read(ROOT / "data" / "holdout_cases.json")
    exclusions = read(ROOT / "data" / "source_exclusions.json")
    outcomes = read(ROOT / "data" / "holdout_outcomes.json")
    baseline = read(ROOT / "records" / "baseline_development.json")
    interval = wilson(selected["correct"], selected["labeled"])
    paired = {name: paired_month_interval(selected, final["results"][name], cases) for name in ("always_up", "previous_market_only", "previous_best_jev")}
    save(ROOT / "records" / "uncertainty.json", {"accuracy_wilson_95": interval, "paired_month_bootstrap": paired})
    lines = ["# Ten iterations of Jev question-strategy optimization", "", f"Completed {now()}. Model pinned to **jev-1.13.0**. Exactly **10** candidate iterations; stopped after iteration 10.", "", f"Best validation configuration: **{selection['selected_iteration']}: {selection['name']}**, {validation['correct']}/{validation['labeled']} correct (**{pct(validation['full_coverage_accuracy'])}**). Fresh 2026 holdout: {selected['correct']}/{selected['labeled']} correct (**{pct(selected['full_coverage_accuracy'])}**), balanced accuracy {pct(selected['balanced_accuracy'])}, Brier {number(selected['brier'])}, forecast coverage {pct(selected['forecast_coverage'])}.", "", f"The 70% full-coverage goal was {'reached' if validation['goal_70_reached'] else 'not reached'} on validation and {'reached' if selected['goal_70_reached'] else 'not reached'} on the fresh holdout. The holdout accuracy's approximate 95% Wilson interval is {pct(interval[0])}–{pct(interval[1])}. This interval assumes independent cases; shared market exposure makes that optimistic.", "", "## What was fixed before the search", "", "The earlier final-test labels were never read by this experiment. Earlier 75 training / 45 validation inputs were reused for development, with 74 valid training labels and one already excluded split-window case. All 30 earlier final cases and original NVIDIA examples were excluded from new tuning and checked for same-stock target-session overlap when selecting fresh cases. Thirty new inputs were frozen before iteration 1: January–June 2026, six per company across NVDA, AAPL, AMD, META and MSFT (five issuer excerpts plus one unrelated NASA control).", "", "This is an accuracy-targeting follow-up: selection maximizes correct/labeled validation cases, treating missing forecasts as incorrect. Ties use balanced accuracy, then lower failure-penalized Brier, then earlier iteration. The earlier benchmark selected by Brier; both probability quality and accuracy are reported here. No target threshold, case membership or outcome was changed to reach 70%.", "", "Entry is the first XNYS regular-session open strictly after the end-of-source-date New York cutoff. Exit is the fifth session close, counting entry as session one. Return is close/open−1: up >+1%, flat inclusive ±1%, down <−1%. Reused frozen exchange_calendars 4.12 labeling logic. Yahoo/yfinance auto_adjust=False, actions=True, repair=False; vendor split-adjusted OHLC excludes cash dividends. Windows containing a split, missing/nonpositive bars, or predeclared split-boundary overlap remain unscored with no replacements after freeze. This predicts subsequent raw returns, not the announcement's initial or causal effect.", "", "Jev sees only input excerpts, company context, and cutoff-safe market observations. Statistical coefficients fit training only. Earlier winning market probabilities are a forecast reference, never a realized label. Per-case outcome labels and exit prices are outside every API request. Adaptive prompt changes use only aggregate validation failure patterns.", "", "## All ten iterations", "", "| # | Branch | Train accuracy | Validation accuracy | Balanced accuracy | Brier ↓ | Coverage | Retained as best |", "|---:|---|---:|---:|---:|---:|---:|---|"]
    rows = []
    for path in sorted((ROOT / "records" / "iterations").glob("*.json")):
        item = read(path)
        val = item["metrics"]["validation"]
        train = item["metrics"]["train"]
        rows.append({"iteration": item["iteration"], "method": item["proposal"]["name"], "train_accuracy": train["full_coverage_accuracy"], "validation_accuracy": val["full_coverage_accuracy"], "validation_balanced_accuracy": val["balanced_accuracy"], "validation_brier": val["brier"], "coverage": val["forecast_coverage"], "retained": item["retained_as_best"]})
        lines.append(f"| {item['iteration']} | {item['proposal']['name']} | {pct(train['full_coverage_accuracy'])} | {pct(val['full_coverage_accuracy'])} ({val['correct']}/{val['labeled']}) | {pct(val['balanced_accuracy'])} | {number(val['brier'])} | {pct(val['forecast_coverage'])} | {'yes' if item['retained_as_best'] else 'no'} |")
    with (ROOT / "results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines += ["", "Retention is relative to earlier candidates. Every unsuccessful candidate is preserved. Separate branch experiments change architecture; iteration 6 changes both feature wording and learner relative to 5, so that comparison cannot isolate a wording effect. Matched no-Jev comparisons isolate the additional feature bundle within each learner.", "", "## Validation baselines", ""]
    lines += metric_table({name: value["validation"] for name,value in baseline.items()})
    lines += ["", "## Fresh holdout: selected once after all tuning", ""] + metric_table(final["results"])
    lines += ["", "Only the selected configuration, its required component branches and the fixed baselines ran on this holdout. Other candidates were not ranked on these outcomes, and no changes followed the result.", "", "### Does Jev add value?", ""]
    for name in ("always_up", "previous_market_only", "previous_best_jev"):
        other = final["results"][name]
        diff = selected["full_coverage_accuracy"]-other["full_coverage_accuracy"]
        brier = selected["brier"]-other["brier"] if selected["brier"] is not None and other["brier"] is not None else None
        info = paired[name]
        lines.append(f"Compared with {name}, accuracy difference is {100*diff:+.1f} percentage points and Brier difference is {number(brier)} (negative favors the selected method). Paired six-month block bootstrap 95% intervals: accuracy {pct(info['accuracy_difference_95_interval'][0])} to {pct(info['accuracy_difference_95_interval'][1])}; Brier {number(info['brier_difference_95_interval'][0])} to {number(info['brier_difference_95_interval'][1])}.")
        lines.append("")
    if selected["full_coverage_accuracy"] <= max(final["results"][name]["full_coverage_accuracy"] for name in ("always_up", "previous_market_only", "previous_best_jev")):
        lines.append("This search does not demonstrate an accuracy advantage over the strongest fixed comparison. An attractive validation score alone does not establish predictive value.")
    else:
        lines.append("The selected method has higher observed accuracy than the fixed comparisons on this small holdout. Treat this as tentative retrospective evidence, not proof of stable predictive value; inspect the uncertainty intervals and test prospectively.")
    lines += ["", "## Branch proposals and stage graphs", "", "Exact instructions, option definitions, before-run expectations, aggregate feedback, parent selection and timestamps are in records/proposals/01.json through 10.json. questions.py is the editable prompt library. The winning fully resolved proposal is also in frozen/selection.json.", "", "1. Input + pre-cutoff market → direct three-class forecast.", "2. Input → six atomic business questions → self-describing answers + original input → return forecast.", "3. Input → nine mechanism questions → economic relevance gate → market fallback or continuation/reversal forecast.", "4. Input → independent bull/bear evidence → neutral adjudication.", "5. Input → 24 horizon features → training-only balanced logistic regression with 10 market features.", "6. Input → 24 pricing features → training-only depth-two decision tree; minimum leaf 12.", "7. Input → P(return <−1%) and P(return ≤+1%) → deterministic three-class probabilities.", "8. Input → reversed-option wording → equal probability average with the best earlier direct branch.", "9. Reuse iteration-6 features → unsupported-news market fallback, else bearish / relative-momentum / neutral question selected from pre-cutoff observations.", "10. Equal probability average of the three best earlier validation candidates; no tuned weights.", "", "Atomic answers are named and passed forward with their original question and option definitions. Features: seven evidence probabilities; for each revenue/cash/surprise/continuation/margin channel, favorable-minus-adverse, mixed and unknown probabilities; realized-action probability; missing-response indicator (24). Version 1 leaves the absent priced-reaction feature at zero. Logistic C=.05, class_weight=balanced; no parameter grid. The shallow tree uses max_depth=2, min_samples_leaf=12. Both have median imputation and market-only ablations.", "", "For iteration 7, down=lower CDF, flat=upper−lower, up=1−upper. If lower>upper, both CDFs are pooled at their mean and the conflict is recorded. Valid API outputs are never silently renormalized. Equal ensembles require every component, preserving missing coverage. Multiclass Brier is the mean sum of the three squared probability errors (range 0–2); lower is better. Confusion matrices use actual rows and predicted columns. Balanced accuracy is mean class recall. Missing forecasts are incorrect for the 70% goal and incur Brier 2 for selection.", "", "## Errors, abstention and uncertainty", "", "Selected holdout confusion matrix (actual rows, predicted columns):", "", "| Actual \\ Predicted | up | flat | down |", "|---|---:|---:|---:|"]
    for actual in LABELS:
        row = selected["confusion_matrix"][actual]
        lines.append(f"| {actual} | {row['up']} | {row['flat']} | {row['down']} |")
    abstention = selected["abstention_policy"]
    lines += ["", f"Separate selective policy, max probability ≥0.60: coverage {pct(abstention['coverage_of_labeled'])}, conditional accuracy {pct(abstention['conditional_accuracy'])}. This cannot satisfy the full-coverage goal by hiding difficult cases.", "", "Largest confident holdout errors:", ""]
    case_map = {case["case_id"]: case for case in cases}
    failures = sorted((row for row in selected["rows"] if row["correct"] is False), key=lambda row: row["brier"], reverse=True)[:6]
    for row in failures:
        case = case_map[row["case_id"]]
        title = case["articles"][0]["title"].replace("\n", " ")
        lines.append(f"- {row['case_id']}: {title}. Predicted {row['prediction']}, actual {row['actual']}, return {pct(row['return'])}; probabilities {row['probabilities']}.")
    lines += ["", "Repeated optimization on only 45 validation cases can overfit the validation set. The fresh holdout has only 30 scheduled cases and six month blocks. Stocks share macro exposure, issuer language is promotional, and calendar dates do not establish what the market expected. Historical excerpts were downloaded today; first-observed is actual retrieval, and exact historical text versions remain uncertain. Company profiles are static source descriptions rather than a verified point-in-time fundamentals database. Jev may have memorized historical information despite instructions not to use it. All results are retrospective evidence.", "", "## Coverage and records", "", f"Development inputs: {len(dev)}; valid training labels 74/75 and validation labels 45/45. Fresh inputs: {len(cases)}; label statuses {dict(Counter(value['status'] for value in outcomes.values()))}; forecast coverage {pct(selected['forecast_coverage'])}. Source exclusions before freeze: {len(exclusions)} (full reasons in data/source_exclusions.json). No exclusions were introduced after inspecting returns. All 30 fresh articles are publisher excerpts, not proven historical full text. Company counts: {dict(Counter(case['company']['ticker'] for case in cases))}.", "", f"API cache: {audit['unique_requests']} unique requests, {audit['attempts']} total attempts, {audit['rejected_attempts']} rejected attempts, {audit['failed_requests']} exhausted requests. Strict response/model/schema validation and identical-request retries (maximum three) were fixed before experiments. All attempts remain in records/api_cache. Original experiment preservation: {audit['previous_files']['files_checked']} existing files checked, zero changed. Dataset, strategy, model and selection hashes are in frozen/; records/verification.json replays final labels and scores and audits request keys.", "", "## Reproduction and modification", "", "Run from the repository root with Python 3.13 and the existing environment:", "", "```powershell", "python -B -m jev_benchmark_lab.question_search_10.run test", "python -B -m jev_benchmark_lab.question_search_10.run verify", "python -B -m jev_benchmark_lab.question_search_10.run report", "```", "", "The saved run is closed: iterate refuses after selection and final refuses after its completed result. Cached inputs, raw API responses, probabilities, historical prices and deterministic label replay reproduce these results without new calls. For a separate research run, copy the small source package into a new folder and freeze a new protocol and holdout before prepare → test → iterate → final → report. Do not delete the frozen selection or reuse this holdout for tuning.", "", "Main functions: data_sets.prepare selects and freezes real sources without prices; core.safe_state allowlists request inputs; questions.definitions defines the staged question graphs; search.predict_case executes one case; search.fit fits training-only models; search.iterate records exactly ten development candidates and selects once; search.final applies that frozen choice to fresh cases; reporting.verify recomputes final labels/scores and checks preservation. The fixed scorer remains ../evaluate.py.", "", "## Prospective procedure", "", "Choose future companies/dates and sampling rules in a new protocol first. At each cutoff save the actual article text, source and first-observed timestamp, point-in-time company context and market observations; run the frozen winning questions/model; write a timestamped, hashed forecast before the entry open. Keep the forecast immutable (for example a dated Git commit or append-only external receipt). After the fifth session close acquire prices and label using the same function. Evaluate at the predeclared sample size without choosing a new strategy from interim outcomes. Treat any later prompt change as a new version with a new untouched evaluation period.", ""]
    (ROOT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print("REPORT", str(ROOT / "REPORT.md"), flush=True)
