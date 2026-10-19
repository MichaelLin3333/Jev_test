"""Bounded development, frozen selection, and one final holdout evaluation."""
from pathlib import Path
import hashlib
import json
import math
import pickle
import sys
import platform
import importlib.metadata as metadata
from collections import Counter
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from .common import ROOT, now, read, save, digest, protocol, protection_manifest, audit_protection
from . import data, strategy, evaluate

def snapshot_sources():
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.glob("*.py")}

def freeze_protocol():
    folder=ROOT/"frozen";folder.mkdir(exist_ok=True)
    if not (folder/"protocol.json").exists():
        save(folder/"existing_files.json",protection_manifest())
        save(folder/"protocol.json",protocol())
        save(folder/"protocol_stamp.json",{"frozen_at":now(),"sha256":digest(protocol()),"new_returns_acquired":False})
    elif digest(protocol())!=digest(read(folder/"protocol.json")): raise ValueError("Frozen protocol changed")

def smoke():
    freeze_protocol()
    out=ROOT/"records"/"smoke.json"
    if out.exists():
        print("Smoke already recorded; use saved evidence",flush=True);return read(out)
    # Both dates belong to training. No final-test prices or outcomes are fetched.
    row={"ticker":"AAPL","date":"2023-05-09","title":"Apple introduces Final Cut Pro and Logic Pro for iPad","url":"https://www.apple.com/newsroom/2023/05/apple-brings-final-cut-pro-and-logic-pro-to-ipad/"}
    article=data.article_text(row)
    case=data.case_from_article("AAPL","train",article,"smoke-AAPL-2023-05-09")
    save(ROOT/"data"/"smoke_cases.json",[case])
    stock=data.download_prices("AAPL","2023-06-01","smoke");spy=data.download_prices("SPY","2023-06-01","smoke")
    outcome=data.label_case(case,stock);features=data.market_features(case,stock,spy)
    results={s:strategy.run_case(case,s) for s in ("legacy","single_direct","features")}
    metrics={s:evaluate.compact(evaluate.score([case["case_id"]],{case["case_id"]:r.get("probabilities")},{case["case_id"]:outcome})) for s,r in results.items() if s!="features"}
    record={"at":now(),"case_id":case["case_id"],"training_only":True,"outcome":outcome,"market_features":features,"results":results,"metrics":metrics,"passed":outcome["status"]=="ok" and all(r["status"]=="ok" for r in results.values()) and all(x is not None for x in features)}
    save(out,record)
    print(json.dumps({"smoke_passed":record["passed"],"training_case":case["case_id"],"source_chars":len(article["text"]),"valid_stages":{s:r["status"] for s,r in results.items()},"label_status":outcome["status"]}),flush=True)
    if not record["passed"]:raise ValueError("End-to-end smoke failed; inspect its preserved record")

def dataset():
    data.verify_frozen()
    return read(ROOT/"data"/"cases.json")

def fit_model(cases,outcomes,market,text=None,C=0.1):
    ids=[c["case_id"] for c in cases if c["split"]=="train" and outcomes.get(c["case_id"],{}).get("label") in evaluate.LABELS]
    x=[];y=[]
    for cid in ids:
        row=list(market[cid])
        if text is not None:row+=list(text[cid]["features"])
        x.append([np.nan if v is None else v for v in row]);y.append(outcomes[cid]["label"])
    if len(set(y))<2:raise ValueError("Training labels have fewer than two classes")
    model=make_pipeline(SimpleImputer(strategy="median",keep_empty_features=True),StandardScaler(),LogisticRegression(C=C,max_iter=2000,random_state=1701))
    model.fit(np.asarray(x,dtype=float),y)
    return model

def predict_model(model,cases,market,text=None):
    ids=[c["case_id"] for c in cases];x=[]
    for cid in ids:
        row=list(market[cid])
        if text is not None:row+=list(text[cid]["features"])
        x.append([np.nan if v is None else v for v in row])
    probabilities=model.predict_proba(np.array(x,dtype=float));classes=list(model.classes_)
    return {cid:{label:float(p[classes.index(label)]) if label in classes else 0.0 for label in evaluate.LABELS} for cid,p in zip(ids,probabilities)}

def constant_predictions(cases,p):return {c["case_id"]:p.copy() for c in cases}

def develop():
    cases=dataset()
    if (ROOT/"frozen"/"selection.json").exists():raise ValueError("Selection already frozen; development is closed")
    dev=[c for c in cases if c["split"]!="test"]
    # This function never opens a test outcome file, and no such file is created here.
    outcomes,market=data.prepare_prices("development")
    splits={s:[c["case_id"] for c in dev if c["split"]==s] for s in ("train","validation")}
    prior=evaluate.training_prior(splits["train"],outcomes);save(ROOT/"frozen"/"training_prior.json",prior)
    predictions={};models={};results={};experiments=[]
    def record(name,preds,iteration=None,change=None,reason=None,expectation=None,parent=None):
        predictions[name]=preds
        metrics={s:evaluate.score(ids,preds,outcomes) for s,ids in splits.items()}
        results[name]={s:evaluate.compact(m) for s,m in metrics.items()}
        for s,m in metrics.items():save(ROOT/"records"/"development"/(name+"_"+s+".json"),m)
        save(ROOT/"records"/"development"/(name+"_predictions.json"),preds)
        if iteration is not None:
            previous=min([x for x in results if x in ("legacy","single_direct","shrunk_direct","market_plus_jev","market_plus_jev_strong") and x!=name],key=lambda x:results[x]["validation"]["selection_brier_failure_penalized"])
            retained=metrics["validation"]["selection_brier_failure_penalized"]<results[previous]["validation"]["selection_brier_failure_penalized"]
            experiments.append({"iteration":iteration,"strategy":name,"parent":parent,"observed_failure":reason,"change":change,"expected_behavior_before_run":expectation,"validation":evaluate.compact(metrics["validation"]),"previous_best_jev":previous,"previous_best_validation":results[previous]["validation"]["selection_brier_failure_penalized"],"retained_as_best_jev":retained})
            save(ROOT/"records"/"experiment_log.json",experiments)
        print("RESULT",name,json.dumps(results[name]["validation"]),flush=True)
    for label in evaluate.LABELS:record("always_"+label,constant_predictions(dev,{x:float(x==label) for x in evaluate.LABELS}))
    record("training_prior",constant_predictions(dev,prior))
    market_model=fit_model(dev,outcomes,market,C=0.1);models["market_only"]=market_model
    record("market_only",predict_model(market_model,dev,market))
    old=strategy.run_batch(dev,"legacy");record("legacy",{cid:r.get("probabilities") for cid,r in old.items()})
    before=results["legacy"]["validation"]
    proposal={"iteration":1,"strategy":"single_direct","observed_failure":f"Legacy validation Brier={before['brier']}, coverage={before['forecast_coverage']}; intermediary interpretations have no learned mapping to post-opening returns.","change":"Remove event/economics/magnitude calls; keep the same final question and source.","expected":"Simpler orchestration may reduce propagated interpretation errors; improvement is uncertain."}
    save(ROOT/"records"/"proposals"/"01_single_direct.json",proposal)
    direct=strategy.run_batch(dev,"single_direct")
    record("single_direct",{cid:r.get("probabilities") for cid,r in direct.items()},1,proposal["change"],proposal["observed_failure"],proposal["expected"],"legacy")
    conf=[max(p.values()) for cid,p in predictions["single_direct"].items() if p and cid in splits["validation"]]
    proposal={"iteration":2,"strategy":"shrunk_direct","observed_failure":f"Single-direct mean maximum validation probability={float(np.mean(conf)) if conf else None}; observed accuracy={results['single_direct']['validation']['accuracy']}. Forecast probabilities have no in-domain calibration fit.","change":"Blend each direct probability 50/50 with training class frequencies.","expected":"Lower confidence may improve Brier even if the most likely label remains unchanged."}
    save(ROOT/"records"/"proposals"/"02_shrunk_direct.json",proposal)
    shrunk={cid:{x:0.5*p[x]+0.5*prior[x] for x in evaluate.LABELS} if p else None for cid,p in predictions["single_direct"].items()}
    record("shrunk_direct",shrunk,2,proposal["change"],proposal["observed_failure"],proposal["expected"],"single_direct")
    proposal={"iteration":3,"strategy":"market_plus_jev","observed_failure":f"Direct and shrunk validation Brier={results['single_direct']['validation']['brier']}, {results['shrunk_direct']['validation']['brier']}; business interpretation does not itself learn this return target.","change":"Add atomic Jev features to the identical market-only logistic model, C=0.1; fit training only.","expected":"If text carries incremental information, the paired model should beat market-only validation Brier; otherwise reject added complexity."}
    save(ROOT/"records"/"proposals"/"03_market_plus_jev.json",proposal)
    text=strategy.run_batch(dev,"features")
    feature_model=fit_model(dev,outcomes,market,text,C=0.1);models["market_plus_jev"]=feature_model
    record("market_plus_jev",predict_model(feature_model,dev,market,text),3,proposal["change"],proposal["observed_failure"],proposal["expected"],"market_only")
    train_brier=results["market_plus_jev"]["train"]["brier"];val_brier=results["market_plus_jev"]["validation"]["brier"]
    proposal={"iteration":4,"strategy":"market_plus_jev_strong","observed_failure":f"Text-model training Brier={train_brier}, validation Brier={val_brier}, using only {len(splits['train'])} training cases. Additional features risk unstable fitting.","change":"Change only C from 0.1 to 0.01; cache the same Jev judgments; also fit matched C=0.01 market-only ablation.","expected":"Stronger shrinkage may reduce variance; no guarantee of validation improvement."}
    save(ROOT/"records"/"proposals"/"04_market_plus_jev_strong.json",proposal)
    strong_market=fit_model(dev,outcomes,market,C=0.01);models["market_only_strong"]=strong_market
    record("market_only_strong",predict_model(strong_market,dev,market))
    strong=fit_model(dev,outcomes,market,text,C=0.01);models["market_plus_jev_strong"]=strong
    record("market_plus_jev_strong",predict_model(strong,dev,market,text),4,proposal["change"],proposal["observed_failure"],proposal["expected"],"market_plus_jev")
    names=["legacy","single_direct","shrunk_direct","market_plus_jev","market_plus_jev_strong"]
    selected=min(names,key=lambda x:(results[x]["validation"]["selection_brier_failure_penalized"],names.index(x)))
    champion=min(results,key=lambda x:results[x]["validation"]["selection_brier_failure_penalized"])
    modeldir=ROOT/"frozen"/"models";modeldir.mkdir(parents=True,exist_ok=True)
    for name,model in models.items():
        with (modeldir/(name+".pkl")).open("wb") as f:pickle.dump(model,f)
    save(ROOT/"records"/"development_results.json",results)
    selection={"selected_at":now(),"selected_jev_strategy":selected,"validation_champion_including_baselines":champion,"selection_rule":"minimum failure-penalized validation Brier; earlier iteration breaks Jev ties","validation_brier":results[selected]["validation"]["selection_brier_failure_penalized"],"training_prior":prior,"dataset_sha256":digest(cases),"source_files":snapshot_sources(),"model_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in modeldir.glob("*.pkl")},"final_test_ids":read(ROOT/"frozen"/"dataset.json")["splits"]["test"],"matched_ablation":"market_only_strong" if selected=="market_plus_jev_strong" else "market_only","final_test_labels_seen":False,"models_refit_on_validation":False}
    save(ROOT/"frozen"/"selection.json",selection)
    save(ROOT/"records"/"environment.json",{"recorded_at":now(),"python":sys.version,"platform":platform.platform(),"dependencies":{m:metadata.version(m) for m in ("numpy","pandas","scikit-learn","yfinance","exchange-calendars","requests","beautifulsoup4")}})
    audit_protection()
    print("SELECTED AND FROZEN",selected,"overall validation champion",champion,"Final labels not acquired.",flush=True)

def final():
    cases=dataset();selection=read(ROOT/"frozen"/"selection.json")
    done=ROOT/"records"/"final_results.json"
    if done.exists():raise ValueError("Final evaluation already completed; no second evaluation permitted")
    if snapshot_sources()!=selection["source_files"]:raise ValueError("Prediction/evaluation code changed after selection")
    for name,h in selection["model_sha256"].items():
        if hashlib.sha256((ROOT/"frozen"/"models"/name).read_bytes()).hexdigest()!=h:raise ValueError("Fitted model changed")
    lock=ROOT/"frozen"/"final_started.json"
    if not lock.exists():save(lock,{"started_at":now(),"selection_sha256":digest(selection),"policy":"Single final pass; interrupted requests may resume from exact caches without changing selection"})
    test=[c for c in cases if c["split"]=="test"];ids=[c["case_id"] for c in test]
    outcomes,market=data.prepare_prices("final");prior=selection["training_prior"]
    predictions={}
    for label in evaluate.LABELS:predictions["always_"+label]=constant_predictions(test,{x:float(x==label) for x in evaluate.LABELS})
    predictions["training_prior"]=constant_predictions(test,prior)
    def model(name,text=None):
        with (ROOT/"frozen"/"models"/(name+".pkl")).open("rb") as f: fitted=pickle.load(f)
        return predict_model(fitted,test,market,text)
    predictions["market_only"]=model("market_only")
    legacy=strategy.run_batch(test,"legacy");predictions["legacy"]={cid:r.get("probabilities") for cid,r in legacy.items()}
    chosen=selection["selected_jev_strategy"]
    if chosen in ("single_direct","shrunk_direct"):
        direct=strategy.run_batch(test,"single_direct");p={cid:r.get("probabilities") for cid,r in direct.items()}
        predictions[chosen]=p if chosen=="single_direct" else {cid:{x:0.5*v[x]+0.5*prior[x] for x in evaluate.LABELS} if v else None for cid,v in p.items()}
    elif chosen.startswith("market_plus_jev"):
        text=strategy.run_batch(test,"features");predictions[chosen]=model(chosen,text)
        if selection["matched_ablation"]!="market_only":predictions[selection["matched_ablation"]]=model(selection["matched_ablation"])
    results={name:evaluate.score(ids,p,outcomes) for name,p in predictions.items()}
    for name,result in results.items():save(ROOT/"records"/"final"/(name+".json"),result)
    save(ROOT/"records"/"final_predictions.json",predictions)
    save(done,{"completed_at":now(),"selection_sha256":digest(selection),"single_final_pass":True,"selected_jev_strategy":chosen,"results":{n:evaluate.compact(r) for n,r in results.items()}})
    audit_protection()
    print("FINAL",json.dumps({n:evaluate.compact(r) for n,r in results.items()}),flush=True)
