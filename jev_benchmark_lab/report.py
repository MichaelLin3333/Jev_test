"""Readable results and export tables; no model fitting or strategy selection."""
from collections import Counter
import csv
import json
import numpy as np
from .common import ROOT,now,read,save,protocol,audit_protection
from .evaluate import compact

def number(x):return "—" if x is None else f"{x:.4f}"
def percent(x):return "—" if x is None else f"{100*x:.1f}%"

def paired_uncertainty(cases,selected,baseline):
    """Descriptive month-block bootstrap; the small number of months limits it."""
    left={r["case_id"]:r for r in selected["rows"] if r["brier"] is not None}
    right={r["case_id"]:r for r in baseline["rows"] if r["brier"] is not None}
    bymonth={}
    for case in cases:
        cid=case["case_id"]
        if cid in left and cid in right:
            month=case["window"]["entry_session"][:7]
            bymonth.setdefault(month,[]).append(left[cid]["brier"]-right[cid]["brier"])
    keys=sorted(bymonth);rng=np.random.default_rng(1701);bootstrap=[]
    for _ in range(5000):
        sampled=rng.choice(keys,size=len(keys),replace=True)
        values=[v for k in sampled for v in bymonth[k]]
        bootstrap.append(float(np.mean(values)))
    values=[v for k in keys for v in bymonth[k]]
    return {"delta_brier_selected_minus_baseline":float(np.mean(values)),"paired_cases":len(values),"calendar_month_blocks":len(keys),"descriptive_95_percentile_interval":[float(x) for x in np.percentile(bootstrap,[2.5,97.5])],"replicates":5000,"seed":1701,"caution":"Few month blocks and historical text uncertainty; not a claim of independent or prospective observations."}

def write_report():
    cases=read(ROOT/"data"/"cases.json");coverage=read(ROOT/"data"/"coverage.json")
    dev=read(ROOT/"records"/"development_results.json")
    selection=read(ROOT/"frozen"/"selection.json")
    final=read(ROOT/"records"/"final_results.json") if (ROOT/"records"/"final_results.json").exists() else None
    log=read(ROOT/"records"/"experiment_log.json")
    chosen=selection["selected_jev_strategy"];baseline=selection["matched_ablation"]
    lines=["# Jev benchmark-and-improvement experiment", "",f"Report generated {now()}. Retrospective exploratory evidence; five companies, no prospective validation.","","## Finding",""]
    if final:
        m=final["results"][chosen];market=final["results"].get(baseline,final["results"]["market_only"]);prior=final["results"]["training_prior"]
        better=m["selection_brier_failure_penalized"]<min(market["selection_brier_failure_penalized"],prior["selection_brier_failure_penalized"])
        lines += [f"The selected Jev strategy was **{chosen}**, frozen using validation results before test prices or labels were acquired. Its final-test Brier was **{number(m['brier'])}**, versus **{number(market['brier'])}** for the matched market-only predictor and **{number(prior['brier'])}** for training class frequencies.","",("It achieved a lower point-estimate Brier than these baselines on this small final sample. This is tentative incremental evidence, not established predictive skill or prospective profitability." if better else "This experiment does **not demonstrate added value beyond the baselines**. The selected Jev strategy did not beat both the matched market-only model and the training-frequency baseline on final-test Brier. An unfavorable result was accepted without further tuning."),""]
    else:lines += ["Final evaluation is not complete; no claim about held-out value is made.",""]
    lines += ["## Dataset and exclusions","",f"Intended 150 cases; collected **{len(cases)}**: {sum(not c['control'] for c in cases)} issuer-news items and {sum(c['control'] for c in cases)} unrelated NASA astronomy controls. Source issuers: NVDA, AAPL, AMD, META and MSFT. Range: 2023-01-01 through 2025-12-31. This fixed five-company selection uses accessible primary-source archives; GOOG, TSM and TSLA were not included.","","| Company | Train | Validation | Final test |","|---|---:|---:|---:|"]
    for t in protocol()["universe"]:lines.append("| "+t+" | "+" | ".join(str(sum(c['company']['ticker']==t and c['split']==s for c in cases)) for s in ("train","validation","test"))+" |")
    exclusions=read(ROOT/"data"/"exclusions.json");reasons=Counter(r["reason"] for r in exclusions)
    development_outcomes=read(ROOT/"data"/"development_outcomes.json")
    test_outcomes=read(ROOT/"data"/"test_outcomes.json") if final else {}
    label_details={}
    for s in ("train","validation","test"):
        selected_cases=[c for c in cases if c["split"]==s]
        source=test_outcomes if s=="test" else development_outcomes
        label_details[s]={"scheduled":len(selected_cases),"statuses":dict(Counter(source.get(c['case_id'],{}).get('status','not_acquired') for c in selected_cases)),"classes":dict(Counter(source[c['case_id']]['label'] for c in selected_cases if source.get(c['case_id'],{}).get('label')))}
    save(ROOT/"records"/"label_coverage.json",label_details)
    lines += ["",f"Recorded {len(exclusions)} source/selection exclusions: "+"; ".join(f"{k}: {v}" for k,v in reasons.items())+".","","Each issuer's nearby releases were conservatively grouped in seven-day blocks; one article represents a block. Sampling used source dates and a fixed seeded rule, never future returns. Legacy source URLs and nearby NVIDIA dates were removed. Each case is assigned to one chronological split. Earlier cases whose target window crosses the next split are purged before freezing. No post-freeze failure is replaced.","","All article bodies were retrieved during this experiment, not captured contemporaneously. **Every historical text version is marked uncertain**. Raw HTML, extraction selectors, text hashes, publication metadata and actual first-observed times are saved. Updated pages may contain later information; a historical date alone cannot resolve this. Publisher excerpts are labeled and no AI summaries substitute for source text.","","Primary newsrooms have a promotional bias and limited adverse independent reporting. Unrelated controls are deliberately easy relevance checks. This is not a representative or exhaustive general-news benchmark.","","## Frozen target and scoring","","Entry is the first XNYS regular-session open strictly after the end-of-day New York cutoff. Exit is the fifth session close, counting entry as one. Return = exit close / entry open - 1. Up is above +1%, down below -1%, and flat includes both boundaries. This measures subsequent raw price movement, excluding initial overnight repricing and cash dividends; it is not causal attribution or trading profit.","","Yahoo/yfinance OHLC are vendor split-adjusted, with auto_adjust=False, actions=True, repair=False. Windows with a reported split are unscored. Missing/invalid target prices are explicit failures, never interpolated. Exchange calendar handles holidays and early closes. Prices and library versions are archived.","","Brier = mean(sum((class probability - one-hot observed class)^2)) across the three classes; lower is better, range 0–2. Covered-case metrics are reported alongside response and label coverage. Validation ranking charges missing forecasts loss 2, preventing failed cases from improving selection. Abstention is a separate max-probability >=0.60 policy, not the flat class.","","## Baselines and complete validation experiment table","","All statistical predictors, imputers and scalers were fit on training cases only. No validation refit was performed. Market features are 1/5/20-session stock and SPY returns, 20-session volatilities, and 5/20-session relative returns, using closes no later than each cutoff.","","| Method | Train Brier | Validation Brier | Validation accuracy | Balanced accuracy | Forecast coverage | Selection Brier |","|---|---:|---:|---:|---:|---:|---:|"]
    # Keep post-freeze data failures visible without changing membership.
    position=lines.index("## Frozen target and scoring")
    details=["**Price-label coverage:** "+"; ".join(f"{s}: {d['statuses']}, class counts {d['classes']}" for s,d in label_details.items())+". The frozen denominator includes every selected case.",""]
    lines[position:position]=details
    for n,r in dev.items():
        m=r["validation"];lines.append(f"| {n} | {number(r['train']['brier'])} | {number(m['brier'])} | {percent(m['accuracy'])} | {percent(m['balanced_accuracy'])} | {percent(m['forecast_coverage'])} | {number(m['selection_brier_failure_penalized'])} |")
    lines += ["",f"Selected Jev strategy: **{chosen}**. Overall validation champion including baselines: **{selection['validation_champion_including_baselines']}**. Four candidates were evaluated; no hidden search or test-driven tuning was performed.","","| Iteration | Change | Previous best Jev | Retained as best Jev? |","|---|---|---|---|"]
    for e in log:lines.append(f"| {e['iteration']} | {e['strategy']}: {e['change']} | {e['previous_best_jev']} | {'yes' if e['retained_as_best_jev'] else 'no'} |")
    for e in log:lines += ["",f"**Iteration {e['iteration']}: {e['strategy']}**", "", "Observed issue: "+e["observed_failure"],"","Expected before running: "+e["expected_behavior_before_run"]]
    if final:
        lines += ["","## One final evaluation","","Only predeclared baselines, the selected Jev strategy, and its matched no-Jev ablation were evaluated. Losing candidates were not run on the final set. No configuration changed after this result.","","| Method | Brier | Accuracy | Balanced accuracy | Forecast coverage | Label coverage |","|---|---:|---:|---:|---:|---:|"]
        for n,m in final["results"].items():lines.append(f"| {n} | {number(m['brier'])} | {percent(m['accuracy'])} | {percent(m['balanced_accuracy'])} | {percent(m['forecast_coverage'])} | {percent(m['label_coverage'])} |")
        lines += ["","### Confusion matrices and abstention","","Matrices below use actual rows and predicted columns in up/flat/down order."]
        for n,m in final["results"].items():
            matrix=m["confusion_matrix"];a=m["abstention_policy"]
            lines += ["",f"**{n}:** "+json.dumps([[matrix[r][c] for c in ("up","flat","down")] for r in ("up","flat","down")])+f". Abstention-policy coverage {percent(a['coverage_of_labeled'])}, conditional accuracy {percent(a['conditional_accuracy'])}."]
        selected_rows=read(ROOT/"records"/"final"/(chosen+".json"))["rows"]
        worst=sorted([r for r in selected_rows if r["brier"] is not None],key=lambda r:r["brier"],reverse=True)[:6]
        lookup={c["case_id"]:c for c in cases}
        lines += ["","## Important final failure cases","","| Case | Source title | Actual return | Prediction | Brier |","|---|---|---:|---|---:|"]
        for r in worst:
            c=lookup[r["case_id"]];lines.append(f"| {r['case_id']} | {c['articles'][0]['title'].replace('|','/')} | {percent(r['return'])} | {r['prediction']} | {number(r['brier'])} |")
        lines += ["","These are error descriptions after the frozen final evaluation, not prompts for another tuning round. Individual cases and probabilities are in records/final/*.json."]
        # Per-company and control diagnostics are descriptive only, after final selection.
        selected_preds=read(ROOT/"records"/"final_predictions.json")[chosen]
        outcomes=read(ROOT/"data"/"test_outcomes.json")
        from .evaluate import score
        subgroup={}
        for key,subset in [(t,[c for c in cases if c["split"]=="test" and c["company"]["ticker"]==t]) for t in protocol()["universe"]]+[("unrelated_controls",[c for c in cases if c["split"]=="test" and c["control"]]),("issuer_news",[c for c in cases if c["split"]=="test" and not c["control"]])]:
            subgroup[key]=compact(score([c["case_id"] for c in subset],selected_preds,outcomes))
        save(ROOT/"records"/"final_subgroups.json",subgroup)
        matched_name=selection["matched_ablation"]
        if matched_name not in final["results"]:matched_name="market_only"
        uncertainty={n:paired_uncertainty([c for c in cases if c["split"]=="test"],read(ROOT/"records"/"final"/(chosen+".json")),read(ROOT/"records"/"final"/(n+".json"))) for n in (matched_name,"training_prior")}
        save(ROOT/"records"/"paired_uncertainty.json",uncertainty)
        lines += ["","## Uncertainty in the final comparison","","A descriptive bootstrap resamples whole calendar months, preserving same-month cross-company co-movement better than treating every article as independent. There are very few month blocks, so these intervals remain exploratory."]
        for n,u in uncertainty.items():lines += ["",f"Selected minus {n}: mean Brier difference {u['delta_brier_selected_minus_baseline']:.4f}, descriptive 95% interval [{u['descriptive_95_percentile_interval'][0]:.4f}, {u['descriptive_95_percentile_interval'][1]:.4f}], {u['paired_cases']} paired cases across {u['calendar_month_blocks']} months. Negative favors the selected Jev strategy."]
    cache=list((ROOT/"records"/"api_cache").glob("*.json"));attempts=[]
    for p in cache:attempts+=read(p)["attempts"]
    rejected=[a for a in attempts if a["status"]!="ok"]
    usage=sum(a.get("raw_response",{}).get("usage",{}).get("input_tokens",0) for a in attempts)
    feature_records=list((ROOT/"records"/"predictions"/"features").glob("*.json"));features=[read(p) for p in feature_records]
    tone=Counter(r.get("answers",{}).get("revenue",{}).get("choice","failed") for r in features)
    lines += ["","## API execution and remaining uncertainty","",f"Pinned model: {protocol()['model']}. {len(attempts)} HTTP attempts across {len(cache)} unique cached requests; {len(rejected)} rejected/error attempts preserved. Reported input tokens: {usage:,}. Estimated token charge at the checked $0.042/million input-token rate: ${usage*0.042/1000000:.4f}; actual account billing was not queried and unmetered failures may add cost.","",f"Feature-reading revenue judgments over the cases that used that strategy: {dict(tone)}. These are model classifications, not human-verified sentiment labels or financial ground truth.","","The API validates concrete model identity, complete typed answers, finite values, probability sums within 1e-6, selected options and usage. Up to three identical attempts are allowed only for protocol/transport failures. Rejected raw responses are retained and never normalized. Exact request hashes cache unchanged judgments. Missing Jev features use an explicit missingness indicator with training-only median imputation; feature-call coverage remains visible in the records.","","Historical holdouts cannot remove training-data knowledge. Article revisions, source selection, five-issuer concentration, contemporaneous market expectations missing from inputs, overlapping cross-company macro exposures and a small holdout constrain interpretation. No result here establishes trading profitability.","","## Reproduce and understand the implementation","","Run from the Jev repository root with Python 3.11+ and requirements from requirements.txt. TYPESAFE_API_KEY is read locally through the existing key helper; credentials are never written to request artifacts.","","```powershell","python -B -m unittest jev_benchmark_lab.test_lab -v","python -B -m jev_benchmark_lab.lab smoke","python -B -m jev_benchmark_lab.lab collect","python -B -m jev_benchmark_lab.lab freeze","python -B -m jev_benchmark_lab.lab develop","python -B -m jev_benchmark_lab.lab final","python -B -m jev_benchmark_lab.lab report","python -B -m jev_benchmark_lab.lab audit","```","","The saved run is immutable: collection/development/final commands refuse to overwrite frozen/completed phases. A future independent replication needs a fresh lab copy and a new benchmark version; do not rerun this final set as an optimization loop. Source caches permit exact replay; re-downloading does not guarantee the same data vintage.","","- data.py: discovery, source extraction, conservative grouping, fixed splits, calendars, archived prices and labels.","- strategy.py: strict input allowlist, Jev transport/cache, original staged baseline and atomic features. Signed economic features equal P(favorable)-P(adverse); unknown probability is retained separately.","- evaluate.py: fixed scoring, coverage and abstention policy. No model fitting.","- experiment.py: training-only models, four recorded candidate iterations, frozen selection and one final pass.","- records/experiment_log.json: every candidate, expected behavior, validation result and retention decision.","","## Prospective follow-up procedure","","Record a new article exactly as observed, its retrieval timestamp, source metadata and company context; set the cutoff no earlier than actual receipt. Before any subsequent outcome exists, run the frozen selected strategy and save input hash, model version, full probabilities and forecast timestamp. Retain all consecutive eligible events, including failures. After five regular sessions, obtain prices and score with this unchanged evaluator. Do not change a forecast after observing returns. Aggregate future results only after a preregistered event count or end date.","","## Sources","","- [TypeSafe model versions and pricing](https://docs.typesafe.ai/models)","- [TypeSafe typed API contract](https://docs.typesafe.ai/api)","- [yfinance history parameters](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.history.html)","- [Exchange calendars](https://github.com/gerrymanoim/exchange_calendars)","- Individual publisher URLs, raw source snapshots and retrieval timestamps are embedded in data/cases.json.",""]
    provenance_position=lines.index("Primary newsrooms have a promotional bias and limited adverse independent reporting. Unrelated controls are deliberately easy relevance checks. This is not a representative or exhaustive general-news benchmark.")
    lines[provenance_position:provenance_position]=["Selection reserved risk/adverse-action and financial-results title categories where available, then filled with dates spread across each period. Those title categories are not return labels. Every saved model input is conservatively labeled publisher_excerpt, including uncapped body extractions. Public HTML snapshots are saved as decoded UTF-8; the HTTP-payload hash is retained separately, so newline/encoding conversion can make it differ from the local snapshot's byte hash.",""]
    (ROOT/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    rows=[]
    for phase,models in [("validation",{n:r['validation'] for n,r in dev.items()}),("final",final["results"] if final else {})]:
        for name,m in models.items():rows.append({"phase":phase,"method":name,**{k:m[k] for k in ("scheduled","labeled","valid_forecasts","brier","accuracy","balanced_accuracy","forecast_coverage","selection_brier_failure_penalized")}})
    with (ROOT/"results.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    save(ROOT/"records"/"api_usage.json",{"attempts":len(attempts),"unique_requests":len(cache),"rejected_attempts":len(rejected),"reported_input_tokens":usage,"estimated_usd":usage*0.042/1000000,"feature_revenue_class_counts":dict(tone)})
    print("Report written:",ROOT/"REPORT.md",flush=True)
    audit_protection()
