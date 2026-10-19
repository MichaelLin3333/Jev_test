"""Verify the completed run without changing cases, predictions or scores."""
import hashlib
import io
import json
import unittest
from collections import Counter
from datetime import datetime
from ..common import ROOT,REPO,now,read,save,digest,audit_protection
from .. import data,evaluate

def legacy_windows():
    windows=[]
    for path in (REPO/"jev_model_eval"/"qualitative_news_tests_2026-10-17").glob("*.json"):
        if "previous_attempt" in path.name: continue
        dates=set()
        def visit(value):
            if isinstance(value,dict):
                for key,item in value.items():
                    if key=="decision_time" and isinstance(item,str): dates.add(item)
                    if key not in ("response","raw_response"): visit(item)
            elif isinstance(value,list):
                for item in value: visit(item)
        visit(read(path))
        for date in dates:
            # Older out-of-range observations cannot overlap the 2023–2025 pilot.
            if not "2022-01-01"<=date[:10]<="2026-12-01": continue
            windows.append((path.stem,data.target_window(date)))
    return windows

def forbidden_state_keys(value):
    bad=[]
    if isinstance(value,dict):
        for key,item in value.items():
            if key in {"label","actual_label","outcomes","return","entry_open","exit_close","future_prices"}: bad.append(key)
            bad+=forbidden_state_keys(item)
    elif isinstance(value,list):
        for item in value: bad+=forbidden_state_keys(item)
    return bad

def main():
    data.verify_frozen()
    cases=read(ROOT/"data"/"cases.json")
    selection=read(ROOT/"frozen"/"selection.json")
    source_mismatches=[name for name,h in selection["source_files"].items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=h]
    assert not source_mismatches,source_mismatches
    target_mismatches=[];market_mismatches=[]
    prices={phase:{ticker:read(ROOT/"data"/"prices"/phase/(ticker+".json"))["bars"] for ticker in list(data.CONTEXT)+["SPY"]} for phase in ("development","final")}
    outcomes={"development":read(ROOT/"data"/"development_outcomes.json"),"final":read(ROOT/"data"/"test_outcomes.json")}
    features={"development":read(ROOT/"data"/"development_market_features.json"),"final":read(ROOT/"data"/"test_market_features.json")}
    for case in cases:
        phase="final" if case["split"]=="test" else "development"
        cid=case["case_id"];ticker=case["company"]["ticker"]
        assert data.target_window(case["decision_time"])==case["window"]
        assert len(case["window"]["sessions"])==5
        assert datetime.fromisoformat(case["window"]["entry_open_at"])>datetime.fromisoformat(case["decision_time"])
        actual=data.label_case(case,prices[phase][ticker]);expected=outcomes[phase][cid]
        if actual!=expected: target_mismatches.append(cid)
        cutoff_date=case["decision_time"][:10]
        stock=[r for r in prices[phase][ticker] if r["date"]<=cutoff_date]
        spy=[r for r in prices[phase]["SPY"] if r["date"]<=cutoff_date]
        if data.market_features(case,stock,spy)!=features[phase][cid]:market_mismatches.append(cid)
    assert not target_mismatches,target_mismatches
    assert not market_mismatches,market_mismatches
    cache=list((ROOT/"records"/"api_cache").glob("*.json"));leaks=[];pins=[];invalid_cache_keys=[]
    for path in cache:
        item=read(path);request=item["request"]
        if forbidden_state_keys(request["state"]):leaks.append(path.name)
        if request["model"]!=read(ROOT/"protocol.json")["model"]:pins.append(path.name)
        if digest(request)!=path.stem:invalid_cache_keys.append(path.name)
    assert not leaks,leaks
    assert not pins,pins
    assert not invalid_cache_keys,invalid_cache_keys
    for path in (ROOT/"data"/"prices"/"development").glob("*.json"):
        assert max(r["date"] for r in read(path)["bars"])<"2025-07-01"
    for path in (ROOT/"data"/"prices"/"final").glob("*.json"):
        assert read(path)["retrieved_at"]>selection["selected_at"]
    overlap=[]
    old=legacy_windows()
    for case in cases:
        if case["split"]!="test" or case["company"]["ticker"]!="NVDA":continue
        for name,window in old:
            shared=sorted(set(case["window"]["sessions"])&set(window["sessions"]))
            if shared:overlap.append({"new_case":case["case_id"],"control":case["control"],"previous_case":name,"shared_sessions":shared})
    suite=unittest.defaultTestLoader.loadTestsFromName("jev_benchmark_lab.test_lab")
    output=io.StringIO();result=unittest.TextTestRunner(stream=output,verbosity=2).run(suite)
    assert result.wasSuccessful(),output.getvalue()
    preservation=audit_protection()
    record={"verified_at":now(),"software_checks_passed":True,"offline_tests_passed":result.testsRun,"cases_rechecked":len(cases),"api_requests_checked":len(cache),"labels_recomputed_from_saved_prices":True,"market_features_recomputed_without_post_cutoff_bars":True,"realized_outcome_keys_found_in_api_states":leaks,"model_pin_mismatches":pins,"changed_prediction_source_files":source_mismatches,"preservation":preservation,"holdout_window_overlaps_with_prior_work":overlap,"holdout_independence_issue_count":len(overlap),"scores_or_membership_changed":False,"final_evaluation_repeated":False,"audit_conclusion":"A small Brier improvement is uncertain; all selected final class predictions are up. One control's target window overlaps prior work, weakening holdout independence; it remains in the frozen result."}
    save(ROOT/"records"/"verification.json",record)
    (ROOT/"records"/"offline_test_output.txt").write_text(output.getvalue(),encoding="utf-8")
    note=["## Post-run verification and independence limitation","",f"All {result.testsRun} offline checks passed. All {len(cases)} saved targets and pre-cutoff market feature vectors were recomputed from archived prices. All {len(cache)} unique Jev request states were checked for realized outcome keys and model pins. Prediction code, frozen cases and 124 pre-existing project files remained unchanged.","","**The selected model predicted up on all 30 final cases.** Its 43.3% accuracy and 33.3% balanced accuracy match the constant-up classifier. The observed gain is in probability scores, not improved directional classification. Both descriptive Brier-difference intervals include zero.",""]
    if overlap:
        note += ["**The independence audit found an exclusion gap:** the legacy-date rule was applied to issuer news but not the preselected astronomy controls. One final NVIDIA control uses a new source article but shares four trading sessions with an earlier NVIDIA case. This weakens the independence of the final holdout. The run should not be presented as a fully clean unseen-outcome validation.",""]
        for item in overlap:note += [f"- New case `{item['new_case']}` overlaps `{item['previous_case']}` on {', '.join(item['shared_sessions'])}."]
        note += ["","No case was removed, no score or model was retuned, and no second final evaluation was run after finding this issue. A future benchmark must apply legacy-window exclusion to every source, including controls, before freezing. Any stronger conclusion requires genuinely prospective inputs and outcomes.",""]
    marker="<!-- post-run-verification -->"
    report=ROOT/"REPORT.md";text=report.read_text(encoding="utf-8").split(marker)[0].rstrip()
    report.write_text(text+"\n\n"+marker+"\n"+"\n".join(note),encoding="utf-8")
    save(ROOT/"records"/"verification_note.json",{"text":"\n".join(note)})
    print(json.dumps({k:record[k] for k in ("software_checks_passed","offline_tests_passed","cases_rechecked","api_requests_checked","holdout_independence_issue_count","scores_or_membership_changed")}))

if __name__=="__main__":main()
