"""Ten recorded candidate evaluations; no access to the old final-test labels."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import hashlib
import pickle
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier, export_text
from .core import ROOT, OLD, LABELS, read, save, now, digest, protocol, safe_state, call_jev, average, metrics, rank, code_hashes, verify_previous, previous_strategy
from .questions import definitions, feature_vector, FEATURE_COUNT, ordered_probabilities, enrich_market_scale
from .data_sets import verify_dataset, acquire_holdout_outcomes

def load_market_model():
    path = OLD / "frozen" / "models" / "market_only_strong.pkl"
    expected = read(OLD / "frozen" / "selection.json")["model_sha256"][path.name]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    with path.open("rb") as stream:
        return pickle.load(stream)

def model_predictions(model, cases, market, text=None):
    matrix = []
    for case in cases:
        cid = case["case_id"]
        row = list(market[cid]) + (text[cid]["features"] if text is not None else [])
        matrix.append([np.nan if value is None else value for value in row])
    probabilities = model.predict_proba(np.asarray(matrix, dtype=float))
    classes = list(model.classes_)
    return {case["case_id"]: {label: float(row[classes.index(label)]) if label in classes else 0.0 for label in LABELS} for case, row in zip(cases, probabilities)}

def fit(cases, outcomes, market, text, kind):
    train = [case for case in cases if case["split"] == "train" and outcomes[case["case_id"]]["label"] in LABELS]
    matrix = []
    target = []
    for case in train:
        cid = case["case_id"]
        values = list(market[cid]) + (text[cid]["features"] if text is not None else [])
        matrix.append([np.nan if value is None else value for value in values])
        target.append(outcomes[cid]["label"])
    estimator = LogisticRegression(C=0.05, class_weight="balanced", max_iter=2000, random_state=2718) if kind == "logistic" else DecisionTreeClassifier(max_depth=2, min_samples_leaf=12, class_weight="balanced", random_state=2718)
    model = make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True), StandardScaler(), estimator)
    model.fit(np.array(matrix, dtype=float), target)
    return model, [case["case_id"] for case in train]

def self_describing(questions, response):
    return {name: {"question": question["instructions"], "criteria": question.get("criteria"), "answer": response["answers"][name]} for name, question in questions.items()}

def api_stage(state, questions, requests):
    response, key = call_jev(state, questions)
    requests.append(key)
    return response

def predict_case(case, market, base, specification, previous):
    iteration = specification["iteration"]
    state = enrich_market_scale(safe_state(case, market, base))
    stages = specification["questions"]
    requests = []
    result = {"case_id": case["case_id"], "iteration": iteration, "status": "failed", "probabilities": None, "requests": requests}
    if iteration in (2, 3, 4):
        name = {2: "business", 3: "mechanism", 4: "perspectives"}[iteration]
        response = api_stage(state, stages[name], requests)
        if response is None:
            return result
        result["assessments"] = response["answers"]
        state["prior_assessments"] = self_describing(stages[name], response)
        if iteration == 3:
            answers = response["answers"]
            if min(answers["relevance"]["noul"], answers["economic_event"]["noul"]) < 0.5:
                result.update(status="ok", probabilities=base, route="unsupported_news_market_fallback")
                return result
            continuation = answers["continuation"]["probabilities"]
            state["route"] = "supported_positive_continuation" if continuation["positive"] > continuation["negative"] else "negative_or_uncertain_continuation"
            result["route"] = state["route"]
    if iteration in (5, 6):
        response = api_stage(state, stages["features"], requests)
        if response is None:
            result["features"] = [None] * (FEATURE_COUNT-1) + [1.0]
            return result
        result.update(status="ok", features=feature_vector(response["answers"]), assessments=response["answers"])
        return result
    if iteration == 7:
        response = api_stage(state, stages["cdf"], requests)
        if response is None:
            return result
        probabilities, conflict = ordered_probabilities(response["answers"]["below_negative_band"]["noul"], response["answers"]["at_most_positive_band"]["noul"])
        result.update(status="ok", probabilities=probabilities, cdf_order_conflict=conflict)
        return result
    if iteration == 9:
        earlier = previous[6]
        answers = earlier.get("assessments")
        requests.extend(earlier["requests"])
        if not answers:
            return result
        if min(answers["relevance"]["noul"], answers["economic_event"]["noul"]) < 0.5:
            result.update(status="ok", probabilities=base, route="unsupported_news_market_fallback")
            return result
        state["prior_assessments"] = {name: {"question": stages["features"][name]["instructions"], "criteria": stages["features"][name].get("criteria"), "answer": answer} for name, answer in answers.items()}
        values = state["pre_cutoff_market"]
        if values["spy_return_5"] is not None and values["spy_return_5"] < -0.02:
            route = "bearish_forecast"
        elif values["relative_return_20"] is not None and values["relative_return_20"] > 0.10:
            route = "reversal_forecast"
        else:
            route = "neutral_forecast"
        result["route"] = route
        question = stages[route]
    else:
        question = stages["forecast"]
    response = api_stage(state, question, requests)
    if response is None:
        return result
    probabilities = response["answers"]["forecast"]["probabilities"]
    if iteration == 8:
        probabilities = average([probabilities, previous[specification["parent"]].get("probabilities")])
    result.update(status="ok" if probabilities else "failed", probabilities=probabilities)
    return result

def run_batch(cases, market, base, specification, records):
    iteration = specification["iteration"]
    folder = ROOT / "records" / "predictions" / f"iteration_{iteration:02d}"
    output = {}
    def one(case):
        cid = case["case_id"]
        signature = digest({"specification": specification, "case": safe_state(case, market[cid], base[cid])})
        path = folder / (cid + ".json")
        if path.exists():
            cached = read(path)
            assert cached["input_sha256"] == signature
            return cached
        previous = {number: values[cid] for number, values in records.items() if cid in values}
        value = predict_case(case, market[cid], base[cid], specification, previous)
        value["input_sha256"] = signature
        value["recorded_at"] = now()
        save(path, value)
        return value
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(one, case) for case in cases]
        for count, future in enumerate(as_completed(futures), 1):
            value = future.result()
            output[value["case_id"]] = value
            if count % 30 == 0 or count == len(cases):
                print("ITERATION", iteration, count, "/", len(cases), "case records", flush=True)
    return output

def adaptive_note(best):
    if best is None:
        return ""
    recall = best["recall_by_actual_class"]
    notes = []
    if recall.get("down") is not None and recall["down"] < 0.25:
        notes.append("Explicitly examine a plausible adverse economic path and bearish market/relative trend; favorable issuer language must not eliminate the down outcome.")
    if recall.get("up") is not None and recall["up"] < 0.25:
        notes.append("Do not discard ordinary upward market continuation merely because the article's incremental impact is unknown.")
    flat = sum(row["flat"] for row in best["confusion_matrix"].values())
    if flat > 0.4 * best["labeled"]:
        notes.append("A prior evaluation exposed overuse of flat. Allocate flat mass using the narrow threshold and observed volatility, not missing evidence.")
    return " ".join(notes)

def specification(iteration, summaries):
    branch = copy.deepcopy(protocol()["branches"][iteration-1])
    branch["questions"] = definitions(iteration)
    branch["created_at"] = now()
    best_id = max(summaries, key=lambda number: (*rank(summaries[number]["validation"]), -number)) if summaries else None
    best = summaries[best_id]["validation"] if best_id else None
    branch["previous_best"] = best_id
    branch["observed_failure"] = ("Earlier direct forecasts overused flat; the earlier selected feature model predicted up for every case." if best is None else f"Best development strategy {best_id} has full-coverage validation accuracy {best['full_coverage_accuracy']:.4f}, balanced accuracy {best['balanced_accuracy']:.4f}; target is 0.70. Confusion matrix: {best['confusion_matrix']}.")
    branch["expected_behavior"] = {
        1: "Reduce erroneous near-certain flat forecasts using actual pre-cutoff trend and volatility.",
        2: "Separate business interpretation from price prediction without losing uncertainty or original question definitions.",
        3: "Use market probabilities for non-economic news and isolate continuation evidence for meaningful news.",
        4: "Improve adverse-case recognition by evaluating bull and bear evidence independently before adjudication.",
        5: "Learn a return mapping from horizon-specific text features rather than assuming business sign equals price sign.",
        6: "A shallow tree may capture interactions between economic evidence and market regime with limited capacity.",
        7: "Cumulative questions may make the narrow neutral band clearer and reduce categorical framing bias.",
        8: "Reverse phrasing and equal averaging may reduce option-order and wording sensitivity.",
        9: "Regime-specific questions may improve bearish and reversal cases while retaining a no-evidence fallback.",
        10: "Equal averaging of retained branches may improve robustness without optimizing more weights.",
    }[iteration]
    note = adaptive_note(best)
    branch["adaptive_wording_from_aggregate_feedback"] = note
    for stage, questions in branch["questions"].items():
        if "forecast" in stage:
            for question in questions.values():
                question["instructions"] += " " + note
    if iteration == 8:
        eligible = [number for number in summaries if number in (1,2,3,4,7)]
        branch["parent"] = max(eligible, key=lambda number: (*rank(summaries[number]["validation"]), -number))
    if iteration == 9:
        branch["parent"] = 6
    if iteration == 10:
        branch["parents"] = sorted(summaries, key=lambda number: (*rank(summaries[number]["validation"]), -number), reverse=True)[:3]
    return branch

def constant_predictions(cases, probabilities):
    return {case["case_id"]: probabilities.copy() for case in cases}

def iterate():
    verify_dataset()
    if (ROOT / "frozen" / "selection.json").exists():
        raise ValueError("Ten-iteration search already completed; no further tuning")
    assert not (ROOT / "data" / "holdout_outcomes.json").exists()
    assert not (ROOT / "data" / "holdout_prices").exists()
    cases = read(ROOT / "data" / "development_cases.json")
    outcomes = read(ROOT / "data" / "development_outcomes.json")
    market = read(ROOT / "data" / "development_market.json")
    splits = {split: [case["case_id"] for case in cases if case["split"] == split] for split in ("train", "validation")}
    source_file = ROOT / "frozen" / "search_code.json"
    if not source_file.exists():
        save(source_file, code_hashes())
    assert read(source_file) == code_hashes(), "Code changed after search began"
    base = model_predictions(load_market_model(), cases, market)
    prior = read(OLD / "frozen" / "training_prior.json")
    baselines = {"training_prior": constant_predictions(cases, prior), "previous_market_only": base}
    old_predictions = read(OLD / "records" / "development" / "market_plus_jev_strong_predictions.json")
    baselines["previous_best_jev"] = {cid: old_predictions[cid] for cid in splits["train"] + splits["validation"]}
    for label in LABELS:
        baselines["always_" + label] = constant_predictions(cases, {name: float(name == label) for name in LABELS})
    save(ROOT / "records" / "baseline_development.json", {name: {split: metrics(ids, values, outcomes) for split, ids in splits.items()} for name, values in baselines.items()})
    summaries = {}
    records = {}
    proposals = {}
    for iteration in range(1, 11):
        complete = ROOT / "records" / "iterations" / f"{iteration:02d}.json"
        if complete.exists():
            item = read(complete)
            summaries[iteration] = item["metrics"]
            records[iteration] = read(ROOT / "records" / f"iteration_{iteration:02d}_records.json")
            proposals[iteration] = item["proposal"]
            continue
        proposal_path = ROOT / "records" / "proposals" / f"{iteration:02d}.json"
        proposal = read(proposal_path) if proposal_path.exists() else specification(iteration, summaries)
        save(proposal_path, proposal)
        proposals[iteration] = proposal
        print("START ITERATION", iteration, proposal["name"], flush=True)
        if iteration == 10:
            values = {case["case_id"]: {"case_id": case["case_id"], "status": "ok", "probabilities": average([records[parent][case["case_id"]].get("probabilities") for parent in proposal["parents"]]), "parents": proposal["parents"], "requests": []} for case in cases}
        else:
            values = run_batch(cases, market, base, proposal, records)
        ablation = None
        if iteration in (5, 6):
            kind = "logistic" if iteration == 5 else "tree"
            fitted, fitting_ids = fit(cases, outcomes, market, values, kind)
            market_only, _ = fit(cases, outcomes, market, None, kind)
            probabilities = model_predictions(fitted, cases, market, values)
            without_text = model_predictions(market_only, cases, market)
            for cid in values:
                values[cid]["feature_status"] = values[cid]["status"]
                values[cid]["probabilities"] = probabilities[cid]
            folder = ROOT / "frozen" / "models"
            folder.mkdir(parents=True, exist_ok=True)
            for suffix, model in (("", fitted), ("_no_jev", market_only)):
                with (folder / f"iteration_{iteration:02d}{suffix}.pkl").open("wb") as stream:
                    pickle.dump(model, stream)
            save(folder / f"iteration_{iteration:02d}_fit_ids.json", fitting_ids)
            if kind == "tree":
                (folder / "iteration_06_tree.txt").write_text(export_text(fitted[-1]), encoding="utf-8")
            ablation = {split: metrics(ids, without_text, outcomes) for split, ids in splits.items()}
        probabilities = {cid: value.get("probabilities") for cid, value in values.items()}
        result = {split: metrics(ids, probabilities, outcomes) for split, ids in splits.items()}
        previous_best = max(summaries, key=lambda number: (*rank(summaries[number]["validation"]), -number)) if summaries else None
        retained = previous_best is None or rank(result["validation"]) > rank(summaries[previous_best]["validation"])
        item = {"iteration": iteration, "proposal": proposal, "completed_at": now(), "metrics": result, "retained_as_best": retained, "matched_no_jev_ablation": ablation}
        save(ROOT / "records" / f"iteration_{iteration:02d}_records.json", values)
        save(complete, item)
        records[iteration] = values
        summaries[iteration] = result
        val = result["validation"]
        print("RESULT", iteration, "accuracy", round(val["full_coverage_accuracy"],4), "balanced", round(val["balanced_accuracy"] or 0,4), "Brier", round(val["brier"] or 0,4), "coverage", val["forecast_coverage"], "retained", retained, flush=True)
    selected = max(summaries, key=lambda number: (*rank(summaries[number]["validation"]), -number))
    models = ROOT / "frozen" / "models"
    save(ROOT / "frozen" / "selection.json", {"selected_at": now(), "iteration_count": 10, "selected_iteration": selected, "name": proposals[selected]["name"], "metrics": summaries[selected]["validation"], "proposals": proposals, "code_hashes": code_hashes(), "model_hashes": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in models.glob("*.pkl")} if models.exists() else {}, "holdout_labels_seen": False})
    verify_previous()
    print("TEN ITERATIONS COMPLETE; SELECTED", selected, "validation accuracy", summaries[selected]["validation"]["full_coverage_accuracy"], "holdout labels not acquired", flush=True)

def final():
    verify_dataset()
    if (ROOT / "records" / "final.json").exists():
        raise ValueError("Fresh holdout already evaluated; no repeat")
    selection = read(ROOT / "frozen" / "selection.json")
    assert selection["iteration_count"] == 10
    assert selection["code_hashes"] == code_hashes()
    for filename, expected in selection["model_hashes"].items():
        assert hashlib.sha256((ROOT / "frozen" / "models" / filename).read_bytes()).hexdigest() == expected
    save(ROOT / "frozen" / "holdout_started.json", {"started_at": now(), "selection_sha256": digest(selection)})
    cases, outcomes, market = acquire_holdout_outcomes()
    base = model_predictions(load_market_model(), cases, market)
    proposals = {int(key): value for key, value in selection["proposals"].items()}
    records = {}
    def get(iteration):
        if iteration in records:
            return records[iteration]
        proposal = proposals[iteration]
        for parent in proposal.get("parents", []) + ([proposal["parent"]] if "parent" in proposal else []):
            get(parent)
        if iteration == 10:
            values = {case["case_id"]: {"probabilities": average([records[parent][case["case_id"]].get("probabilities") for parent in proposal["parents"]])} for case in cases}
        else:
            values = run_batch(cases, market, base, proposal, records)
        if iteration in (5,6):
            with (ROOT / "frozen" / "models" / f"iteration_{iteration:02d}.pkl").open("rb") as stream:
                model = pickle.load(stream)
            predictions = model_predictions(model, cases, market, values)
            for cid in values:
                values[cid]["probabilities"] = predictions[cid]
        records[iteration] = values
        return values
    chosen = get(selection["selected_iteration"])
    predictions = {"selected": {cid: value.get("probabilities") for cid, value in chosen.items()}, "previous_market_only": base, "training_prior": constant_predictions(cases, read(OLD / "frozen" / "training_prior.json"))}
    for label in LABELS:
        predictions["always_" + label] = constant_predictions(cases, {name: float(name == label) for name in LABELS})
    old_feature_records = {}
    for case in cases:
        old_feature_records[case["case_id"]] = previous_strategy.run_case(case, "features")
    with (OLD / "frozen" / "models" / "market_plus_jev_strong.pkl").open("rb") as stream:
        previous_winner = pickle.load(stream)
    predictions["previous_best_jev"] = model_predictions(previous_winner, cases, market, old_feature_records)
    if selection["selected_iteration"] in (5,6):
        number = selection["selected_iteration"]
        with (ROOT / "frozen" / "models" / f"iteration_{number:02d}_no_jev.pkl").open("rb") as stream:
            ablation = pickle.load(stream)
        predictions["matched_no_jev"] = model_predictions(ablation, cases, market)
    ids = [case["case_id"] for case in cases]
    result = {name: metrics(ids, value, outcomes) for name, value in predictions.items()}
    save(ROOT / "records" / "final_predictions.json", predictions)
    save(ROOT / "records" / "final_case_records.json", {str(number): values for number, values in records.items()})
    save(ROOT / "records" / "final.json", {"completed_at": now(), "selection_sha256": digest(selection), "selected_iteration": selection["selected_iteration"], "results": result})
    verify_previous()
    print("FINAL", {name: {"accuracy": value["full_coverage_accuracy"], "balanced": value["balanced_accuracy"], "Brier": value["brier"], "coverage": value["forecast_coverage"]} for name, value in result.items()}, flush=True)
