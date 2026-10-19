"""Fixed metrics and deterministic price-window labels. Freeze before optimization."""
import math
from .common import protocol

LABELS=["up","flat","down"]

def checked_probabilities(p):
    if not isinstance(p,dict) or set(p)!=set(LABELS):return None
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not 0<=x<=1 for x in p.values()):return None
    if not math.isclose(sum(p.values()),1,abs_tol=1e-6,rel_tol=0):return None
    return p

def score(case_ids,predictions,outcomes):
    """Missing forecasts keep coverage visible and incur max Brier for selection."""
    matrix={actual:{pred:0 for pred in LABELS} for actual in LABELS}
    losses=[];penalized=[];correct=0;eligible=0;accepted=[]
    rows=[]
    for cid in case_ids:
        o=outcomes.get(cid,{});actual=o.get("label")
        p=checked_probabilities(predictions.get(cid))
        row={"case_id":cid,"actual":actual,"return":o.get("return"),"probabilities":p,"prediction":None,"brier":None,"correct":None,"label_status":o.get("status","missing"),"forecast_status":"ok" if p else "missing_or_invalid"}
        if actual in LABELS:
            eligible+=1
            if p is None:penalized.append(2.0)
            else:
                pred=max(LABELS,key=lambda x:p[x]);loss=sum((p[x]-(x==actual))**2 for x in LABELS)
                good=pred==actual;matrix[actual][pred]+=1;correct+=good;losses.append(loss);penalized.append(loss)
                row.update(prediction=pred,brier=loss,correct=good)
                if max(p.values())>=0.60:accepted.append((good,loss))
        rows.append(row)
    recalls={x:matrix[x][x]/sum(matrix[x].values()) if sum(matrix[x].values()) else None for x in LABELS}
    available=[v for v in recalls.values() if v is not None]
    valid_all=sum(checked_probabilities(predictions.get(cid)) is not None for cid in case_ids)
    return {"scheduled":len(case_ids),"labeled":eligible,"label_coverage":eligible/len(case_ids) if case_ids else None,"valid_forecasts":valid_all,"forecast_coverage":valid_all/len(case_ids) if case_ids else None,"scored":len(losses),"brier":sum(losses)/len(losses) if losses else None,"selection_brier_failure_penalized":sum(penalized)/len(penalized) if penalized else None,"accuracy":correct/len(losses) if losses else None,"balanced_accuracy":sum(available)/len(available) if available else None,"recall_by_actual_class":recalls,"confusion_matrix":matrix,"abstention_policy":{"threshold":0.60,"accepted":len(accepted),"coverage_of_labeled":len(accepted)/eligible if eligible else None,"conditional_accuracy":sum(x[0] for x in accepted)/len(accepted) if accepted else None,"conditional_brier":sum(x[1] for x in accepted)/len(accepted) if accepted else None},"rows":rows}

def training_prior(ids,outcomes):
    counts={x:0 for x in LABELS}
    for cid in ids:
        y=outcomes.get(cid,{}).get("label")
        if y in counts: counts[y]+=1
    n=sum(counts.values())
    if n==0:raise ValueError("No training labels; cannot estimate prior")
    return {x:counts[x]/n for x in LABELS}

def compact(metric):return {k:v for k,v in metric.items() if k!="rows"}
