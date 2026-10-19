"""Qualitative interpretations of numbers; one paired rerun, no model fitting."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
import argparse
import copy
import hashlib
import json
import math
import re
import sys
import unittest
import numpy as np

EXISTING = Path(__file__).resolve().parent
sys.path.insert(0,str(EXISTING.parents[1]))
sys.path.insert(0,str(EXISTING/"representation_code.zip"))
from input_representation.storage import StorePath
from input_representation.render import rate_questions
from jev_benchmark_lab import common, strategy, evaluate

class QualPath(StorePath):
    def __truediv__(self,part):
        return QualPath(self.root,self.parts+(str(part),))
    @property
    def parent(self):
        return QualPath(self.root,self.parts[:-1])
    def directory(self):
        folder,prefix=super().directory()
        return folder,prefix.replace("representation_","qualitative_",1)
    def physical(self):
        folder,prefix=self.parent.directory()
        assert folder.is_dir()
        return folder/("QUALITATIVE_REPORT.md" if self.parts==("REPORT.md",) else prefix+self.name)
    def glob(self,pattern):
        folder,prefix=self.directory()
        return [QualPath(self.root,self.parts+(path.name[len(prefix):],)) for path in folder.glob(prefix+pattern)]

ROOT=QualPath(EXISTING)
OLD=EXISTING.parent
REPO=OLD.parent
common.ROOT=ROOT
strategy.ROOT=ROOT
read,save,digest,now=common.read,common.save,common.digest,common.now
LABELS=("up","flat","down")
FILES=("cases","raw_states","summaries","questions","outcomes")

def inputs(name):
    return read(EXISTING/"data"/("representation_"+name+".json"))

def source_hashes():
    paths=[EXISTING/"data"/("representation_"+name+".json") for name in FILES]
    paths += [EXISTING/"records"/"representation_scores.json",EXISTING/"records"/"representation_summarized_prose_records.json",EXISTING/"representation_code.zip"]
    return {str(path.relative_to(EXISTING)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}

def snapshot():
    result={}
    for folder in (OLD,REPO/"jev_news",REPO/"jev_model_eval"):
        for path in folder.rglob("*"):
            if path.is_file() and not path.name.startswith("qualitative_") and path.name!="QUALITATIVE_REPORT.md" and not any(part in path.parts for part in ("__pycache__","yfinance_cache")):
                result[str(path.relative_to(REPO))]=hashlib.sha256(path.read_bytes()).hexdigest()
    return result

def magnitude(value,scale):
    if scale is None or scale<=0:
        return ""
    z=abs(value)/scale
    return "very small" if z<.25 else "modest" if z<.75 else "substantial" if z<1.5 else "strong"

def historical_movement(subject,value,volatility,horizon):
    if value is None:
        return f"{subject}: historical movement was not supplied."
    period={1:"the latest completed session",5:"the recent trading week",20:"the recent trading month"}[horizon]
    if value==0:
        return f"{subject} had no net price change over {period}."
    size=magnitude(value,volatility*math.sqrt(horizon) if volatility is not None else None)
    scale_note=", judged against its recent ordinary variability." if volatility is not None and volatility>0 else ". No usable variability estimate was supplied."
    return f"{subject} showed {('a '+size+' ') if size else 'a '}past {'rise' if value>0 else 'decline'} over {period}"+scale_note

def volatility_words(value):
    if value is None:
        return "not supplied"
    return "relatively subdued" if value<.01 else "moderate" if value<.02 else "elevated" if value<.04 else "very high"

def relative_movement(value,stock_vol,market_vol,horizon):
    if value is None:
        return "The stock's performance relative to the broad market was not supplied."
    if value==0:
        return "The stock matched the broad market over the recent trading window."
    scale=math.sqrt(stock_vol**2+market_vol**2)*math.sqrt(horizon) if stock_vol is not None and market_vol is not None else None
    size=magnitude(value,scale)
    period="week" if horizon==5 else "month"
    return f"Over the recent trading {period}, the stock showed {size+' ' if size else ''}{'outperformance' if value>0 else 'underperformance'} relative to the broad market."

def evidence_words(p):
    if p<=.05:return "almost no support"
    if p<=.20:return "little support"
    if p<.40:return "weak support, leaning against the proposition"
    if p<=.60:return "unresolved evidence, without a clear judgment either way"
    if p<.80:return "moderate support"
    if p<.95:return "strong support"
    return "very strong support"

def preference_words(p):
    if p<.55:return "uncertain, with no clear preference"
    if p<.65:return "only slightly favored"
    if p<.80:return "favored, with meaningful uncertainty"
    if p<.95:return "strongly favored"
    return "very strongly favored"

def confidence_words(p):
    return "low" if p<.40 else "limited" if p<.60 else "fairly high" if p<.80 else "high" if p<.95 else "very high"

MEANINGS={"positive":"a favorable effect","negative":"an adverse effect","mixed":"opposing favorable and adverse effects","unchanged":"explicitly unchanged economics","unknown":"insufficient evidence to establish the direction"}
PROPOSITIONS={"relevance":"the article establishes a direct or specific commercial or policy connection to the target","economic_event":"the source describes a substantive economic action rather than publicity or a calendar notice","materiality":"the source establishes a comparable incremental financial amount"}

def judgment_text(name,answer):
    if answer["type"]=="noul":
        return f"On whether {PROPOSITIONS[name]}, earlier Jev reported {evidence_words(answer['noul'])}. This describes Jev's assessment, not a verified fact."
    probabilities=answer["probabilities"]
    best=answer["choice"]
    text=f"For {name}, earlier Jev's leading interpretation was {MEANINGS[best]}. That interpretation was {preference_words(probabilities[best])}."
    alternatives=[MEANINGS[label]+(" remained a meaningful alternative" if p>=.25 else " remained a weaker alternative") for label,p in probabilities.items() if label!=best and p>=.10]
    if alternatives:
        text+=" "+"; ".join(alternatives)+"."
    text+=f" Jev's separately reported confidence in this business assessment was {confidence_words(answer['confidence'])}."
    if best=="unknown":
        text+=" This is an evidence gap; it does not establish no business effect or an unchanged stock price."
    return text

def reference_text(probabilities):
    best=max(LABELS,key=lambda label:probabilities[label])
    labels={"up":"an upward return beyond the neutral band","flat":"a return inside the narrow neutral band","down":"a downward return beyond the neutral band"}
    text=f"The previously fitted market-only reference model {('had no clear preference but ranked '+labels[best]+' first') if probabilities[best]<.55 else ('favored '+labels[best])}. Its leading outcome was {preference_words(probabilities[best])}."
    alternatives=[labels[label] for label in LABELS if label!=best and probabilities[label]>=.10]
    if alternatives:
        text+=" It still assigned meaningful possibility to "+" and ".join(alternatives)+"."
    return text+" This is a training-only model forecast, not an observed outcome or independent news evidence."

def financial_meaning(text):
    """Interpret explicitly identified percentage types, without inventing materiality."""
    notes=[]
    for kind,value in re.findall(r"\b(gross|operating|net)\s+margin(?:\s+(?:was|of|is))?\s*(?:approximately\s*)?(-?\d+(?:\.\d+)?)\s*%",text,re.I):
        share=float(value)/100
        size="a negative portion" if share<0 else "a small portion" if share<.10 else "a minority" if share<.35 else "roughly half" if share<.65 else "a majority" if share<.90 else "nearly all"
        cost={"gross":"after the cost of goods sold, before operating costs","operating":"after operating costs","net":"after the costs included in net income"}[kind.lower()]
        note=f"One explicitly cited {kind.lower()} margin figure means {size} of revenue remained {cost}. Keep its stated period and accounting basis; this alone is not a new cash-flow estimate."
        if note not in notes:notes.append(note)
    # Only a directly identified revenue-growth percentage gets a growth label.
    for value in re.findall(r"revenue[^.!?\n]{0,65}?\b(?:grew|growth of|increased|up)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*%",text,re.I):
        growth=float(value)/100
        size="slight" if growth<.02 else "modest" if growth<.10 else "substantial" if growth<.30 else "strong"
        note=f"The explicitly cited revenue growth reads as {size} growth under the fixed display categories. Preserve the source's comparison period; growth does not establish an analyst-expectation surprise."
        if note not in notes:notes.append(note)
    return notes[:4]

def qualitative_state(original,summaries,previous=None):
    company=original["company"]
    lines=[f"Target: {company['name']} ({company['ticker']}). {company['profile']}",f"Focal announcement: {original['focal_event']}.",f"Decision cutoff: {original['decision_time']}. Only information available before this cutoff is admissible."]
    for article,summary in zip(original["articles"],summaries):
        lines += [f"Source: {article['title']}. Published: {article['publication_date']}. URL: {article['url']}.","Condensed source facts; other details are omitted: "+summary["text"]]
        notes=financial_meaning(summary["text"])
        if notes:lines += ["Qualitative interpretation of explicitly identified source percentages: "+" ".join(notes)]
    lines += ["The exact historical text version is unverified. This is an incomplete source-based reconstruction.","Expectations: "+original["expectations"]["details"],"No company-wide comparable financial baselines or incremental magnitude inputs were supplied. Do not infer that a large headline amount is material to the target."]
    market=original["pre_cutoff_market"]
    stock_vol=market["stock_volatility_20"]
    spy_vol=market["spy_volatility_20"]
    for subject,prefix,vol in (("The stock","stock",stock_vol),("The broad market (SPY)","spy",spy_vol)):
        lines += [historical_movement(subject,market[f"{prefix}_return_{horizon}"],vol,horizon) for horizon in (1,5,20)]
        lines += [f"{subject}'s recent daily variability was {volatility_words(vol)}. Variability describes the size of ordinary fluctuations, not their future direction."]
    lines += [relative_movement(market[f"relative_return_{horizon}"],stock_vol,spy_vol,horizon) for horizon in (5,20)]
    if market["stock_return_5"] is not None and market["spy_return_5"] is not None and market["stock_return_5"]*market["spy_return_5"]<0:
        lines += ["The stock and broad market moved in opposite directions over the recent week, so their historical directional signals conflict."]
    lines += ["These are coarse descriptions computed from observed historical inputs. Strong past movement or relative strength is not evidence that the next return must continue or reverse.",reference_text(original["base_forecast"]["probabilities"])]
    scale=original.get("volatility_scale",{}).get("five_session_one_sigma_reference")
    if scale is not None:
        relation="much narrower than" if scale>.04 else "narrower than" if scale>.015 else "comparable to or wider than"
        lines += [f"The neutral return band's half-width is {relation} the code-computed ordinary five-session variability scale. An irrelevant article does not eliminate ordinary price movement; this is not a calculated class probability."]
    lines += ["Forecast target: entry is the first regular-session open after the cutoff; exit is the fifth session close, counting entry as session one. Raw return above +1% is up; within inclusive -1% to +1% is flat; below -1% is down. The initial pre-entry reaction is outside this target.","Do not invent analyst consensus, incremental target sales, new corporate cash payments, or an already-priced news reaction."]
    if previous is not None:
        lines += ["Earlier Jev business judgments, translated into their qualitative meaning. They are uncertain model assessments, not established facts. Unknown is missing evidence; it is not no effect and not a flat-price forecast."]
        lines += [judgment_text(name,answer) for name,answer in previous["answers"].items()]
    return "\n\n".join(lines)

def freeze():
    destination=ROOT/"frozen"/"inputs.json"
    if destination.exists():
        check_frozen();print("Frozen qualitative inputs already verified.");return
    states=inputs("raw_states");summaries=inputs("summaries")
    rendered={cid:qualitative_state(state,summaries[cid]) for cid,state in states.items()}
    save(ROOT/"data"/"rendered_states.json",rendered)
    save(ROOT/"frozen"/"previous_files.json",snapshot())
    save(destination,{"frozen_at":now(),"protocol_sha256":digest(read(ROOT/"protocol.json")),"source_files":source_hashes(),"code_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"rendered_states_sha256":digest(rendered),"case_count":150,"previously_seen_outcomes":True})
    print("FROZEN qualitative words for",len(rendered),"cases",flush=True)

def check_frozen():
    value=read(ROOT/"frozen"/"inputs.json")
    assert value["protocol_sha256"]==digest(read(ROOT/"protocol.json"))
    assert value["source_files"]==source_hashes()
    assert value["code_sha256"]==hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    assert value["rendered_states_sha256"]==digest(read(ROOT/"data"/"rendered_states.json"))
    return value

def one_case(cid,states,summaries,questions):
    path=ROOT/"records"/"cases"/"prose"/(cid+".json")
    if path.exists():return read(path)
    value={"case_id":cid,"status":"failed","requests":[],"probabilities":None}
    first,key=strategy.call_jev(qualitative_state(states[cid],summaries[cid]),questions["business"])
    value["requests"].append(key)
    if first is not None:
        value["assessments"]=first["answers"]
        second,key=strategy.call_jev(qualitative_state(states[cid],summaries[cid],first),questions["forecast"])
        value["requests"].append(key)
        if second is not None:value.update(status="ok",probabilities=second["answers"]["forecast"]["probabilities"])
    value["completed_at"]=now();save(path,value)
    return value

def metric(ids,predictions,outcomes):
    result=evaluate.score(ids,predictions,outcomes)
    result["correct"]=sum(row["correct"] is True for row in result["rows"])
    result["full_coverage_accuracy"]=result["correct"]/result["labeled"] if result["labeled"] else 0.
    return result

def run(smoke=False):
    check_frozen()
    if (ROOT/"records"/"scores.json").exists():raise ValueError("Qualitative rerun already completed")
    cases=inputs("cases");states=inputs("raw_states");summaries=inputs("summaries")
    questions={stage:rate_questions(value) for stage,value in inputs("questions").items()}
    selected=sorted((case for case in cases if case["split"]=="train"),key=lambda case:case["decision_time"])[:3] if smoke else cases
    records={}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(one_case,case["case_id"],states,summaries,questions) for case in selected]
        for count,future in enumerate(as_completed(futures),1):
            value=future.result();records[value["case_id"]]=value
            if count%30==0 or count==len(selected):print("QUALITATIVE",count,"/",len(selected),"valid",sum(value["status"]=="ok" for value in records.values()),flush=True)
    if smoke:
        save(ROOT/"records"/"smoke.json",{"completed_at":now(),"ids":list(records),"passed":all(value["status"]=="ok" for value in records.values()),"scope":"transport/schema only, no outcome scoring"});return
    save(ROOT/"records"/"case_records.json",records)
    outcomes=inputs("outcomes");predictions={cid:value["probabilities"] for cid,value in records.items()}
    groups={"all150":[case["case_id"] for case in cases]}
    groups.update({split:[case["case_id"] for case in cases if case["split"]==split] for split in sorted({case["split"] for case in cases})})
    results={name:metric(ids,predictions,outcomes) for name,ids in groups.items()}
    save(ROOT/"records"/"scores.json",{"completed_at":now(),"scores":results})
    print("RESULT",{key:results["all150"][key] for key in ("correct","labeled","full_coverage_accuracy","balanced_accuracy","brier","forecast_coverage")},flush=True)

def verify():
    check_frozen()
    expected=read(ROOT/"frozen"/"previous_files.json");actual=snapshot()
    changed=[name for name,value in expected.items() if actual.get(name)!=value]
    assert not changed,changed
    attempts=rejected=failed=total=0
    for path in (ROOT/"records"/"api_cache").glob("*.json"):
        value=read(path);total+=1
        assert digest(value["request"])==path.stem
        assert isinstance(value["request"]["state"],str)
        attempts+=len(value["attempts"])
        rejected+=sum(attempt.get("status")=="rejected" for attempt in value["attempts"])
        failed+=value["status"]!="ok"
        if value["status"]=="ok":strategy.validate(value["response"],value["request"]["questions"])
    if (ROOT/"records"/"scores.json").exists():
        cases=inputs("cases");outcomes=inputs("outcomes");records=read(ROOT/"records"/"case_records.json")
        assert len(records)==150
        replay=metric([case["case_id"] for case in cases],{cid:value["probabilities"] for cid,value in records.items()},outcomes)
        assert replay==read(ROOT/"records"/"scores.json")["scores"]["all150"]
    result={"verified_at":now(),"passed":True,"previous_files_checked":len(expected),"changed":changed,"unique_requests":total,"attempts":attempts,"rejected_attempts":rejected,"exhausted_requests":failed,"model":"jev-1.13.0","outcomes_outside_renderer":True}
    save(ROOT/"records"/"verification.json",result);print("VERIFIED",result,flush=True)
    return result

def paired(reference,variant,cases):
    ref={row["case_id"]:row for row in reference["rows"]};months={case["case_id"]:case["decision_time"][:7] for case in cases}
    fixed=worsened=0;blocks={}
    for row in variant["rows"]:
        if row["actual"] not in LABELS:continue
        old=ref[row["case_id"]];correct=row["correct"] is True;was=old["correct"] is True
        fixed+=correct and not was;worsened+=was and not correct
        delta=(int(correct)-int(was),(row["brier"] if row["brier"] is not None else 2.)-(old["brier"] if old["brier"] is not None else 2.))
        blocks.setdefault(months[row["case_id"]],[]).append(delta)
    groups=list(blocks.values());rng=np.random.default_rng(2718);draws=[]
    for _ in range(5000):
        sample=[item for index in rng.integers(0,len(groups),len(groups)) for item in groups[index]]
        draws.append(np.mean(sample,axis=0))
    ci=np.quantile(draws,[.025,.975],axis=0)
    return {"fixed":int(fixed),"new_errors":int(worsened),"accuracy_change_95_interval":ci[:,0].tolist(),"brier_change_95_interval":ci[:,1].tolist(),"month_blocks":len(groups)}

def trace(cid,records):
    lines=["# Qualitative wording: complete paired case trace","",cid,"","JSON is pretty-printed; every saved input and output field is included. Only state text is qualitative; returned probabilities remain numerical.",""]
    for name in ("previous_prose","qualitative_meaning"):
        value=read(EXISTING/"records"/"representation_summarized_prose_records.json")[cid] if name=="previous_prose" else records[cid]
        lines += ["## "+name,""]
        for stage,key in enumerate(value["requests"],1):
            cache=read(EXISTING/"records"/("representation_api_"+key+".json")) if name=="previous_prose" else read(ROOT/"records"/"api_cache"/(key+".json"))
            lines += [f"### Stage {stage}: input","","```json",json.dumps(cache["request"],ensure_ascii=False,indent=2),"```","",f"### Stage {stage}: output","","```json",json.dumps(cache.get("response",{"status":cache["status"],"attempts":cache["attempts"]}),ensure_ascii=False,indent=2),"```",""]
    lines += ["## Outcome, evaluator only","","```json",json.dumps(inputs("outcomes")[cid],ensure_ascii=False,indent=2),"```",""]
    (ROOT/"examples"/"apple_full_trace.md").write_text("\n".join(lines),encoding="utf-8")

def report():
    audit=verify();cases=inputs("cases");records=read(ROOT/"records"/"case_records.json")
    result=read(ROOT/"records"/"scores.json")["scores"];prior=read(EXISTING/"records"/"representation_scores.json")["scores"]
    comparison={name:paired(prior[name]["all150"],result["all150"],cases) for name in ("raw_json","summarized_prose")}
    save(ROOT/"records"/"paired_comparisons.json",comparison)
    stages={name:dict(Counter(value["assessments"][name]["choice"] for value in records.values() if value.get("assessments"))) for name in ("revenue","cash","surprise")}
    by_id={case["case_id"]:case for case in cases}
    for name,control in (("issuer",False),("unrelated_controls",True)):
        selected=[value["assessments"]["relevance"]["noul"] for cid,value in records.items() if value.get("assessments") and by_id[cid]["control"]==control]
        stages[name]={"n":len(selected),"relevance_yes_at_least_half":sum(p>=.5 for p in selected),"mean":float(np.mean(selected)) if selected else None}
    save(ROOT/"records"/"intermediate_summary.json",stages)
    tokens={stage:[] for stage in (1,2)}
    for value in records.values():
        for stage,key in enumerate(value["requests"],1):
            cache=read(ROOT/"records"/"api_cache"/(key+".json"))
            if cache["status"]=="ok":tokens[stage].append(cache["response"]["usage"]["input_tokens"])
    pct=lambda value:"n/a" if value is None else f"{100*value:.1f}%"
    num=lambda value:"n/a" if value is None else f"{value:.4f}"
    table={name:prior[name]["all150"] for name in ("raw_json","percent_descriptions","summarized_prose","market_only","always_up")}
    table["qualitative_meaning"]=result["all150"]
    lines=["# Jev qualitative-meaning rerun","",f"Completed {now()}. Pinned jev-1.13.0. Same 150 scheduled cases; 149 usable frozen price labels. All cases were already examined, so this is a paired development comparison.","","## What changed","","The earlier prose renderer spelled out percentages. This rerun interprets their meaning instead: historical movement becomes very small/modest/substantial/strong rises or declines, relative returns become outperformance/underperformance, volatility becomes a variability description, and earlier Jev probabilities become attributed judgments such as weak support or strong evidence of an information gap. Source passages and question sequence are otherwise the same as the preceding prose arm.","","Market and prior-answer numbers are absent from the qualitative state. Source dates, currency amounts, source financial rates and exact +/-1% target boundaries remain literal. Where the excerpt explicitly identifies revenue growth or gross/operating/net margin, an additional sentence explains the qualitative financial meaning. An amount without a comparable baseline is not labeled material.","","The rendering categories were fixed before calls in qualitative_protocol.json. Movement strength uses a code-computed historical variability scale; it does not estimate statistical significance or future direction. Relative performance uses a simple covariance-free display scale, not a verified alpha estimate. Unknown is insufficient evidence, never no effect. Earlier Jev assessments and reference-model forecasts are always attributed rather than asserted as facts.","","No Jev weights or statistical models were fitted. No new sources/prices/outcomes were acquired. Only one qualitative wording configuration was run; no post-score revisions.","","## Results","","| Method | Correct / labeled | Accuracy | Balanced accuracy | Brier (lower better) | Forecast coverage |","|---|---:|---:|---:|---:|---:|"]
    for name,value in table.items():lines.append(f"| {name} | {value['correct']}/{value['labeled']} | {pct(value['full_coverage_accuracy'])} | {pct(value['balanced_accuracy'])} | {num(value['brier'])} | {pct(value['forecast_coverage'])} |")
    lines += ["","## Paired changes",""]
    for name,value in comparison.items():
        old=prior[name]["all150"];new=result["all150"]
        lines += [f"Against {name}: {value['fixed']} corrected cases and {value['new_errors']} new errors. Accuracy change {100*(new['full_coverage_accuracy']-old['full_coverage_accuracy']):+.1f} percentage points; Brier change {(new['selection_brier_failure_penalized']-old['selection_brier_failure_penalized']):+.4f}. Paired month-block bootstrap intervals: accuracy {pct(value['accuracy_change_95_interval'][0])} to {pct(value['accuracy_change_95_interval'][1])}; Brier {num(value['brier_change_95_interval'][0])} to {num(value['brier_change_95_interval'][1])}.",""]
    lines += ["## Intermediate answers","","```json",json.dumps(stages,indent=2),"```","","These are behavior distributions, not independently adjudicated semantic accuracy. Unknown surprise can be appropriate because consensus was absent. Direct issuer relevance and unrelated NASA articles are sanity screens, not complete economic ground truth.","","## Original chronological groups","","These groups are all development comparisons now.","","| Original group | Correct / labeled | Accuracy | Balanced accuracy | Brier |","|---|---:|---:|---:|---:|"]
    for name,value in result.items():
        if name!="all150":lines.append(f"| {name} | {value['correct']}/{value['labeled']} | {pct(value['full_coverage_accuracy'])} | {pct(value['balanced_accuracy'])} | {num(value['brier'])} |")
    lines += ["","## Example and input sizes",""]
    cid="AAPL-2025-02-21-216bbb1456";trace(cid,records)
    old=read(EXISTING/"records"/"representation_summarized_prose_records.json")[cid]
    lines += [f"Apple News+ Food: earlier percentage prose {old['probabilities']}; new qualitative interpretation {records[cid]['probabilities']}. Actual raw return was down. [Complete paired inputs and outputs](qualitative_example_apple_full_trace.md).","",f"Mean accepted input tokens: business stage {np.mean(tokens[1]):.0f}; forecast stage {np.mean(tokens[2]):.0f}. Numerical output probabilities are preserved for scoring.","","## Coverage, limitations and verification","",f"{audit['unique_requests']} unique requests, {audit['attempts']} attempts, {audit['rejected_attempts']} rejected attempts and {audit['exhausted_requests']} exhausted requests. All attempts are saved. {audit['previous_files_checked']} earlier files were hash-checked with zero changes. Scores replayed from the same saved outcomes.","","This intervention combines qualitative binning, explanatory wording and some loss of numerical precision. It cannot isolate a pure formatting effect or establish why Jev changed an answer. The same primary-source excerpts and their uncertain historical versions remain a limitation. Repeated development comparisons cannot establish performance on genuinely unseen future outcomes.","","Full metrics, confusion matrices and separate selective coverage/accuracy are in records/qualitative_scores.json. Forecast coverage is valid forecast count / scheduled cases; a missing forecast counts wrong for full-coverage accuracy and receives maximum Brier 2 for paired comparisons. The one original unscorable price window remains excluded without replacement.","","## Reproduction","","```powershell","python -B jev_benchmark_lab/question_search_10/qualitative_run.pyw test","python -B jev_benchmark_lab/question_search_10/qualitative_run.pyw verify","python -B jev_benchmark_lab/question_search_10/qualitative_run.pyw report","```","","For an unstarted version the sequence is prepare -> test -> smoke -> run -> report. Completed scores close this prediction run. The code, input hashes and rendering categories are frozen in frozen/qualitative_inputs.json and qualitative_protocol.json. New qualitative_ files remain in the existing folders; prior representation_ and older experiment records are unchanged.",""]
    (ROOT/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    save(ROOT/"records"/"summary.json",{"metrics":result["all150"],"paired":comparison,"intermediate":stages,"mean_input_tokens":{str(stage):float(np.mean(values)) for stage,values in tokens.items()}})
    print("REPORT",str(ROOT/"REPORT.md"),flush=True)

class Tests(unittest.TestCase):
    def test_small_negative_is_still_a_decline(self):
        text=historical_movement("Stock",-.001,.02,1)
        self.assertIn("very small past decline",text)
        self.assertNotRegex(text,r"\d|%")
    def test_strong_historical_movement(self):
        self.assertIn("strong",historical_movement("Stock",.10,.02,5))
    def test_relative_weakness(self):
        self.assertIn("underperformance",relative_movement(-.1,.02,.01,20))
    def test_unknown_stays_an_information_gap(self):
        answer={"type":"choice","choice":"unknown","confidence":.9,"probabilities":{"positive":.08,"negative":0.,"mixed":0.,"unchanged":0.,"unknown":.92}}
        text=judgment_text("revenue",answer)
        self.assertIn("insufficient evidence",text);self.assertIn("does not establish no business effect",text)
        self.assertNotRegex(text,r"\d|%")
    def test_weak_yes_not_asserted_as_truth(self):
        text=judgment_text("relevance",{"type":"noul","noul":.31})
        self.assertIn("leaning against",text);self.assertIn("not a verified fact",text)
    def test_exact_thresholds(self):
        self.assertEqual(evidence_words(.05),"almost no support")
        self.assertEqual(evidence_words(.40),"unresolved evidence, without a clear judgment either way")
        self.assertEqual(evidence_words(.95),"very strong support")
    def test_margin_explanation_does_not_invent_cash_flow(self):
        text=" ".join(financial_meaning("Gross margin was 49%."))
        self.assertIn("roughly half",text);self.assertIn("not a new cash-flow estimate",text)
    def test_reference_is_a_forecast(self):
        text=reference_text({"up":.65,"flat":.13,"down":.22})
        self.assertIn("not an observed outcome",text);self.assertNotRegex(text,r"\d|%")
    def test_render_has_qualitative_context_and_literal_target(self):
        states=inputs("raw_states");summaries=inputs("summaries");cid="AAPL-2025-02-21-216bbb1456"
        text=qualitative_state(states[cid],summaries[cid]);self.assertIn("outperformance",text)
        self.assertNotIn("65.1672",text);self.assertNotIn("1.61%",text)
        self.assertIn("above +1%",text)
        self.assertIn("evidence gap",judgment_text("surprise",{"type":"choice","choice":"unknown","confidence":1.,"probabilities":{"unknown":1.}}))

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("command",choices=["test","prepare","smoke","run","report","verify","status"]);args=parser.parse_args()
    if args.command=="test":
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests));raise SystemExit(0 if result.wasSuccessful() else 1)
    if args.command=="prepare":return freeze()
    if args.command=="smoke":return run(smoke=True)
    if args.command=="status":return print("Completed cases:",len(list((ROOT/"records"/"cases"/"prose").glob("*.json"))))
    return globals()[args.command]()

if __name__=="__main__":main()
