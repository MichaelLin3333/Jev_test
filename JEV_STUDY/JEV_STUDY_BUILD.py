"""Read saved evidence and render standalone research figures; no API calls."""
from pathlib import Path
import os
import json
import hashlib
import math
import argparse
import tempfile
from collections import Counter
from datetime import datetime, timezone

HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--repo",type=Path,default=HERE.parent,help="Repository containing the saved experiment folders")
parser.add_argument("--output",type=Path,default=HERE,help="Output directory (defaults to this script's directory)")
args=parser.parse_args()
STAGE=args.output.resolve()
STAGE.mkdir(exist_ok=True)
os.environ["MPLCONFIGDIR"]=str(Path(tempfile.gettempdir())/"jev_study_matplotlib_cache")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np

REPO=args.repo.resolve()
LAB=REPO/"jev_benchmark_lab"
Q=LAB/"question_search_10"
SOURCES={}
def read(path):
    raw=path.read_bytes();SOURCES[str(path.relative_to(REPO)).replace("\\","/")]=hashlib.sha256(raw).hexdigest()
    return json.loads(raw)

LABELS=("up","flat","down")
forced=read(REPO/"jev_model_eval/forced_choice_forecasts_2026-10-18/evaluation.json")
addon=read(REPO/"jev_model_eval/experimental_market_mechanism_addon_2026-10-18/summary.json")
original_qual=read(REPO/"jev_model_eval/qualitative_news_tests_2026-10-17/overview.json")
initial_final={name:read(LAB/"records/final"/(name+".json")) for name in ("market_plus_jev_strong","market_only_strong","training_prior","always_up","legacy")}
initial_uncertainty=read(LAB/"records/paired_uncertainty.json")
new_final=read(Q/"records/final.json")["results"]
new_uncertainty=read(Q/"records/uncertainty.json")
iterations=[read(Q/"records/iterations"/f"{number:02d}.json") for number in range(1,11)]
represent=read(Q/"records/representation_scores.json")["scores"]
qual=read(Q/"records/qualitative_scores.json")["scores"]
qual_pair=read(Q/"records/qualitative_paired_comparisons.json")
repr_stages=read(Q/"records/representation_intermediate_summary.json")
qual_stages=read(Q/"records/qualitative_intermediate_summary.json")
repr_tokens=read(Q/"records/representation_token_lengths.json")
qual_summary=read(Q/"records/qualitative_summary.json")
initial_cases=read(LAB/"data/cases.json")
latest_cases=read(Q/"data/representation_cases.json")
development=read(Q/"data/development_cases.json")
old_ids={case["case_id"] for case in initial_cases};new_ids={case["case_id"] for case in latest_cases}
assert len(old_ids)==len(new_ids)==150 and len(old_ids&new_ids)==120
assert len(old_ids|new_ids)==180

def simplify(metric):
    if "rows" not in metric:return metric
    rows=[row for row in metric["rows"] if row["actual"] in LABELS]
    valid=[row for row in rows if row.get("probabilities")]
    recalls={label:sum(row["actual"]==label and row["correct"] is True for row in rows)/sum(row["actual"]==label for row in rows) for label in LABELS}
    correct=sum(row["correct"] is True for row in rows)
    mean_conf=float(np.mean([max(row["probabilities"].values()) for row in valid]))
    return {"scheduled":metric["scheduled"],"labeled":len(rows),"correct":correct,"full_accuracy":correct/len(rows),"covered_accuracy":sum(row["correct"] is True for row in valid)/len(valid),"reported_balanced_accuracy":metric["balanced_accuracy"],"full_balanced_accuracy":float(np.mean(list(recalls.values()))),"recalls_failure_as_wrong":recalls,"covered_brier":metric["brier"],"penalized_brier":metric["selection_brier_failure_penalized"],"coverage":metric["forecast_coverage"],"valid_labeled_forecasts":len(valid),"mean_leading_probability":mean_conf,"prediction_counts":dict(Counter(row["prediction"] if row["prediction"] else "missing" for row in rows)),"selective":metric["abstention_policy"]}

variant_metrics={name:simplify(represent[name]["all150"]) for name in ("raw_json","percent_descriptions","summarized_prose","market_only","always_up","training_prior")}
variant_metrics["qualitative_meaning"]=simplify(qual["all150"])
actual_counts=Counter(row["actual"] for row in represent["raw_json"]["all150"]["rows"] if row["actual"] in LABELS)
assert dict(actual_counts)=={"up":81,"flat":25,"down":43}
matched={}
for version in ("original_features","business_stage","pricing_features"):
    records=read(Q/"records"/("iteration_02_records.json" if version=="business_stage" else "iteration_06_records.json")) if version!="original_features" else None
    answers={}
    for case in development:
        cid=case["case_id"]
        answers[cid]=read(LAB/"records/predictions/features"/(cid+".json"))["answers"] if records is None else records[cid]["assessments"]
    issuer=[answers[case["case_id"]]["relevance"]["noul"] for case in development if not case["control"]]
    controls=[answers[case["case_id"]]["relevance"]["noul"] for case in development if case["control"]]
    matched[version]={"issuer_n":len(issuer),"issuer_yes":sum(value>=.5 for value in issuer),"control_n":len(controls),"control_yes":sum(value>=.5 for value in controls),"issuer_mean":float(np.mean(issuer)),"control_mean":float(np.mean(controls)),"revenue_choices":dict(Counter(value["revenue"]["choice"] for value in answers.values()))}

cid="AAPL-2025-02-21-216bbb1456"
apple={}
for name,file in (("Direct JSON","iteration_01_records.json"),("Staged JSON","representation_raw_json_records.json"),("Percentages","representation_percent_descriptions_records.json"),("Prose percentages","representation_summarized_prose_records.json"),("Qualitative meaning","qualitative_case_records.json")):
    apple[name]=read(Q/"records"/file)[cid]["probabilities"]
apple_state=read(Q/"data/representation_raw_states.json")[cid]
apple_outcome=read(Q/"data/representation_outcomes.json")[cid]

DATA={"generated_at":datetime.now(timezone.utc).isoformat(),"scope":"Saved experiments only; no new API calls or fit. Sources retained below. Cohorts not pooled.","cohort_overlap":{"original150":len(old_ids),"latest150":len(new_ids),"shared":len(old_ids&new_ids),"union":len(old_ids|new_ids)},"forced27":forced,"addon27":addon,"initial_final":{name:simplify(value) for name,value in initial_final.items()},"initial_paired_uncertainty":initial_uncertainty,"new_final":{name:simplify(value) for name,value in new_final.items()},"new_uncertainty":new_uncertainty,"iterations":[{"number":value["iteration"],"name":value["proposal"]["name"],"train":simplify(value["metrics"]["train"]),"validation":simplify(value["metrics"]["validation"]),"retained":value["retained_as_best"],"no_jev":value.get("matched_no_jev_ablation")} for value in iterations],"representations":variant_metrics,"qualitative_paired":qual_pair,"intermediate":{"matched120":matched,"latest150":repr_stages,"qualitative":qual_stages},"input_tokens":{"representation":repr_tokens,"qualitative":qual_summary["mean_input_tokens"]},"apple":{"predictions":apple,"reference":apple_state["base_forecast"]["probabilities"],"outcome":apple_outcome},"source_sha256":SOURCES}

plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"axes.titlesize":12,"axes.titleweight":"bold","axes.labelcolor":"#26364A","text.color":"#1F2B3D","axes.spines.top":False,"axes.spines.right":False,"axes.edgecolor":"#ADB7C3","figure.facecolor":"white","axes.facecolor":"white","savefig.facecolor":"white"})
NAVY="#183F65";TEAL="#148277";ORANGE="#D08A34";RED="#B84D50";GRAY="#B8C1CB";BLUE="#527DA6"
FILES=[]
def finish(fig,name):
    path=STAGE/name;fig.savefig(path,dpi=170,bbox_inches="tight");plt.close(fig);FILES.append(name)

# 1. Lineage: repeated methods are not independent datasets.
fig,ax=plt.subplots(figsize=(13.2,7.8));ax.set_xlim(0,13);ax.set_ylim(0,8);ax.axis("off")
def box(x,y,w,h,title,text,color):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=.14",linewidth=1.1,edgecolor=color,facecolor=color+"12"))
    ax.text(x+.16,y+h-.22,title,fontsize=12,fontweight="bold",va="top",color=color)
    ax.text(x+.16,y+h-.67,text,fontsize=10,va="top",linespacing=1.5)
box(.2,5.55,12.4,1.7,"Selected NVIDIA cohort: 27 inputs", "Four-stage interpretation → forced-choice forecasts → mechanism add-on\nAll three reuse the same selected cases; 26 unique entry/exit windows. No independent holdout.",NAVY)
box(.2,2.75,5.85,2.0,"Original benchmark: 150 inputs", "2023–2025, five technology companies\n75 training (74 labels) + 45 validation + 30 final\nOriginal final has one overlap with a legacy event.",TEAL)
box(6.75,2.75,5.85,2.0,"Latest benchmark: 150 inputs", "Reuse the original 120 development inputs\nAdd 30 new Jan–Jun 2026 inputs\nTen-iteration choice → one fresh 30-case check",BLUE)
ax.annotate("120 reused",xy=(6.8,4.95),xytext=(5.6,4.95),ha="center",va="center",fontsize=9,arrowprops={"arrowstyle":"->","color":GRAY})
box(6.75,.25,5.85,1.45,"Representation and qualitative reruns", "Reuse that latest 150 after outcomes were seen.\n149 usable price labels; development comparisons.",ORANGE)
ax.annotate("same 150",xy=(9.7,1.82),xytext=(9.7,2.45),ha="center",fontsize=9,arrowprops={"arrowstyle":"->","color":GRAY})
ax.text(.25,1.55,"The two 150-input cohorts share 120 IDs.\nTheir union contains 180 inputs, not 300.\nRepeated prompts add measurements, not new events.",fontsize=11,va="top",linespacing=1.6)
fig.suptitle("Figure 1. How the evidence is related",fontsize=17,fontweight="bold",x=.06,ha="left")
finish(fig,"JEV_STUDY_01_COHORTS.png")

# 2. Compare only within the indicated cohort.
fig,axes=plt.subplots(2,3,figsize=(15,9),layout="constrained")
panels=[("Selected NVIDIA · 27 cases",["Forced\nJev","Mechanism\nadd-on","Always\nup","Always\ndown"],[forced["forced_model"]["accuracy"],addon["addon_metrics"]["accuracy"],forced["constant_baselines"]["up"]["accuracy"],forced["constant_baselines"]["down"]["accuracy"]],[forced["forced_model"]["multiclass_brier_score_sum_over_three_classes"],addon["addon_metrics"]["multiclass_brier_score"],forced["constant_baselines"]["up"]["multiclass_brier_score_sum_over_three_classes"],forced["constant_baselines"]["down"]["multiclass_brier_score_sum_over_three_classes"]]),("Original final · 30 cases",["Jev +\nmarket","Matched\nmarket","Training\nprior","Always\nup"],[initial_final[name]["accuracy"] for name in ("market_plus_jev_strong","market_only_strong","training_prior","always_up")],[initial_final[name]["brier"] for name in ("market_plus_jev_strong","market_only_strong","training_prior","always_up")]),("Fresh 2026 final · 30 cases",["Selected\ndirect Jev","Market\nonly","Training\nprior","Always\nup"],[new_final[name]["accuracy"] for name in ("selected","previous_market_only","training_prior","always_up")],[new_final[name]["brier"] for name in ("selected","previous_market_only","training_prior","always_up")])]
for column,(title,names,accuracy,brier) in enumerate(panels):
    for row,values in enumerate((np.array(accuracy)*100,brier)):
        ax=axes[row,column];bars=ax.bar(range(4),values,color=[NAVY,TEAL,GRAY,GRAY],width=.65)
        ax.set_xticks(range(4),names);ax.set_ylim(0,100 if row==0 else 2)
        ax.grid(axis="y",alpha=.16);ax.set_axisbelow(True)
        if row==0:ax.set_title(title,pad=12)
        if column==0:ax.set_ylabel("Accuracy (%)" if row==0 else "Brier: lower is better")
        ax.bar_label(bars,labels=[f"{value:.1f}%" if row==0 else f"{value:.3f}" for value in values],padding=4,fontsize=10)
fig.suptitle("Figure 3. Forecast performance within each cohort\nDifferent panels use different cases and must not be pooled",fontsize=16,fontweight="bold")
finish(fig,"JEV_STUDY_03_FORECASTS.png")

# 3. All ten strategy iterations, no hindsight re-selection.
names=[f"{value['number']}. "+value["name"].replace("_"," ") for value in DATA["iterations"]]
vals=[100*value["validation"]["full_accuracy"] for value in DATA["iterations"]]
train=[100*value["train"]["full_accuracy"] for value in DATA["iterations"]]
briers=[value["validation"]["penalized_brier"] for value in DATA["iterations"]]
fig,(ax,br)=plt.subplots(1,2,figsize=(14.6,7.2),gridspec_kw={"width_ratios":[1.6,1]},layout="constrained")
y=np.arange(10);ax.barh(y,vals,color=[TEAL if i==0 else BLUE for i in range(10)],height=.56,label="Validation accuracy")
ax.scatter(train,y,color=ORANGE,s=27,label="Training accuracy",zorder=4)
ax.set_yticks(y,names);ax.invert_yaxis();ax.set_xlim(0,100);ax.axvline(70,color=RED,linestyle="--",label="70% objective")
ax.axvline(100*24/45,color=GRAY,linestyle=":",label="Always-up validation")
for i,value in enumerate(vals):ax.text(value+1,i,f"{value:.1f}%",va="center",fontsize=9)
ax.set_xlabel("Accuracy (%), missing forecasts count wrong");ax.legend(loc="lower right",fontsize=8);ax.grid(axis="x",alpha=.14);ax.set_axisbelow(True)
bars=br.barh(y,briers,color=[TEAL if i==6 else GRAY for i in range(10)],height=.56)
br.set_yticks(y,[str(i) for i in range(1,11)]);br.invert_yaxis();br.set_xlim(0,1.05)
br.bar_label(bars,labels=[f"{value:.3f}" for value in briers],padding=4,fontsize=9)
br.set_xlabel("Validation Brier including failure penalties ↓");br.set_title("Threshold questions had best Brier,\nbut were not chosen by the frozen rule",fontsize=11)
fig.suptitle("Figure 5. Ten iterations did not beat the 53.3% accuracy baseline\nSelection used accuracy first, then balanced accuracy; iteration 1 alone went to the fresh test",fontsize=15,fontweight="bold")
finish(fig,"JEV_STUDY_05_SEARCH.png")

# 4. Presentation tradeoffs on the identical 149 labelable cases.
order=("raw_json","percent_descriptions","summarized_prose","qualitative_meaning")
labels=["Raw JSON","Percent\ndescriptions","Prose\npercentages","Qualitative\nmeaning"]
fig,axes=plt.subplots(2,2,figsize=(14,10.5),layout="constrained");x=np.arange(4);width=.34
ax=axes[0,0];a=[100*variant_metrics[name]["full_accuracy"] for name in order];b=[100*variant_metrics[name]["full_balanced_accuracy"] for name in order]
ax.bar(x-width/2,a,width,color=NAVY,label="Full-denominator accuracy");ax.bar(x+width/2,b,width,color=TEAL,label="Mean class recall, failures wrong")
ax.axhline(100*81/149,color=ORANGE,linestyle="--",linewidth=1.2,label="Always-up / market accuracy")
ax.set_ylim(0,75);ax.set_xticks(x,labels);ax.set_ylabel("Percent");ax.set_title("A. No accuracy advantage from presentation changes");ax.legend(fontsize=8)
ax=axes[0,1];values=[variant_metrics[name]["penalized_brier"] for name in order];bars=ax.bar(x,values,color=[GRAY,GRAY,GRAY,TEAL]);ax.bar_label(bars,labels=[f"{value:.3f}" for value in values],padding=4)
ax.axhline(variant_metrics["market_only"]["penalized_brier"],color=ORANGE,linestyle="--",label="Market only");ax.set_ylim(0,1);ax.set_xticks(x,labels);ax.set_ylabel("Brier including missing-response penalty ↓");ax.set_title("B. Qualitative meaning improves probability scoring");ax.legend(fontsize=8)
ax=axes[1,0];conf=[100*variant_metrics[name]["mean_leading_probability"] for name in order];acc=[100*variant_metrics[name]["covered_accuracy"] for name in order]
ax.bar(x-width/2,conf,width,color=BLUE,label="Mean leading probability");ax.bar(x+width/2,acc,width,color=NAVY,label="Accuracy on valid forecasts");ax.set_ylim(0,100);ax.set_xticks(x,labels);ax.set_ylabel("Percent");ax.set_title("C. Predictions become less concentrated");ax.legend(fontsize=8)
ax=axes[1,1];bottom=np.zeros(5);distribution_x=np.arange(5)
for category,color in (("up",TEAL),("flat",ORANGE),("down",NAVY),("missing",RED)):
    counts=np.array([variant_metrics[name]["prediction_counts"].get(category,0) for name in order]+[actual_counts.get(category,0)]);height=100*counts/149
    ax.bar(distribution_x,height,bottom=bottom,color=color,label=category)
    for i,count in enumerate(counts):
        if count>=4:ax.text(i,bottom[i]+height[i]/2,str(count),ha="center",va="center",color="white",fontweight="bold")
    bottom+=height
ax.set_xticks(distribution_x,labels+["Actual\noutcomes"]);ax.set_ylim(0,100);ax.set_ylabel("Share of 149 labeled cases (%)");ax.set_title("D. Less up bias does not ensure more correct answers");ax.legend(fontsize=8,ncol=4,loc="upper center",bbox_to_anchor=(.5,-.14))
for ax in axes.flat:ax.grid(axis="y",alpha=.14);ax.set_axisbelow(True)
fig.suptitle("Figure 6. Input representation changes behavior more than predictive skill\nAll cases were already examined; one qualitative forecast failed and is retained",fontsize=16,fontweight="bold")
finish(fig,"JEV_STUDY_06_REPRESENTATION.png")

# 5. Same-input relevance screen and one full before/after example.
fig,(ax,case_ax)=plt.subplots(1,2,figsize=(14.5,6.6),layout="constrained")
keys=("original_features","business_stage","pricing_features");labs=["Original focused\nfeature questions","Later business\nstage","Rephrased pricing\nfeatures"]
positives=[100*matched[name]["issuer_yes"]/matched[name]["issuer_n"] for name in keys];false=[100*matched[name]["control_yes"]/matched[name]["control_n"] for name in keys];x=np.arange(3)
bars=ax.bar(x-.17,positives,.34,color=NAVY,label="Issuer relevance ≥ half");ax.bar_label(bars,labels=[f"{matched[name]['issuer_yes']}/110" for name in keys],padding=5)
bars=ax.bar(x+.17,false,.34,color=ORANGE,label="Unrelated-control relevance ≥ half");ax.bar_label(bars,labels=[f"{matched[name]['control_yes']}/10" for name in keys],padding=5)
ax.set_xticks(x,labs);ax.set_ylim(0,112);ax.set_ylabel("Percentage of the corresponding group");ax.set_title("A. Question/context bundles change relevance judgments\nSame 120 inputs; not a full semantic-accuracy test",fontsize=11);ax.legend(fontsize=8,loc="lower center",bbox_to_anchor=(.5,-.2))
bottom=np.zeros(len(apple));x=np.arange(len(apple))
for label,color in (("up",TEAL),("flat",ORANGE),("down",NAVY)):
    values=np.array([apple[name][label] for name in apple])*100;case_ax.bar(x,values,bottom=bottom,color=color,label=label)
    for i,value in enumerate(values):
        if value>=6:case_ax.text(i,bottom[i]+value/2,f"{value:.0f}",ha="center",va="center",color="white",fontweight="bold")
    bottom+=values
case_ax.set_xticks(x,["Direct\nJSON","Staged\nJSON","Percent\nformat","Prose\npercent","Qualitative\nmeaning"]);case_ax.set_ylim(0,105);case_ax.set_ylabel("Forecast probability (%)");case_ax.set_title("B. Apple News+ Food: actual return −1.2616% (down)\nAll five variants still selected up",fontsize=11);case_ax.legend(fontsize=8,ncol=3,loc="lower center",bbox_to_anchor=(.5,-.2))
fig.suptitle("Figure 2. Focused interpretation and final prediction are different capabilities",fontsize=16,fontweight="bold")
finish(fig,"JEV_STUDY_02_INTERPRETATION.png")

# 6. Forest chart reads saved descriptive intervals, never assumes independence.
forest=[]
for name,label in (("market_only_strong","Original final: Jev + market minus market only"),("training_prior","Original final: Jev + market minus training prior")):
    item=initial_uncertainty[name]
    forest.append({"label":label,"difference":item["delta_brier_selected_minus_baseline"],"interval":item["descriptive_95_percentile_interval"],"cohort":"original final 30","blocks":6,"color":TEAL})
forest.append({"label":"Fresh final: selected direct Jev minus market only","difference":new_final["selected"]["brier"]-new_final["previous_market_only"]["brier"],"interval":new_uncertainty["paired_month_bootstrap"]["previous_market_only"]["brier_difference_95_interval"],"cohort":"fresh final 30","blocks":6,"color":NAVY})
for name,label in (("raw_json","Development rerun: qualitative minus raw JSON"),("summarized_prose","Development rerun: qualitative minus percentage prose")):
    forest.append({"label":label,"difference":variant_metrics["qualitative_meaning"]["penalized_brier"]-variant_metrics[name]["penalized_brier"],"interval":qual_pair[name]["brier_change_95_interval"],"cohort":"familiar 149 labeled inputs","blocks":34,"color":ORANGE})
DATA["brier_difference_intervals"]=forest
fig,ax=plt.subplots(figsize=(13.8,6.5),layout="constrained")
for i,item in enumerate(forest):
    lo,hi=item["interval"];point=item["difference"]
    ax.errorbar(point,i,xerr=[[point-lo],[hi-point]],fmt="o",color=item["color"],capsize=5,markersize=7,linewidth=2)
    ax.text(.445,i,f"{point:+.3f}  [{lo:+.3f}, {hi:+.3f}]",va="center",fontsize=9)
ax.axvline(0,color=GRAY,linestyle="--");ax.axhspan(2.5,4.5,color=ORANGE,alpha=.06)
ax.set_yticks(range(5),[item["label"] for item in forest]);ax.invert_yaxis();ax.set_xlim(-.19,.68);ax.set_ylim(4.7,-.7)
ax.set_xticks([-.15,-.1,-.05,0,.1,.2,.3,.4]);ax.set_xlabel("Brier difference: negative favors the Jev configuration being compared")
ax.grid(axis="x",alpha=.15);ax.set_axisbelow(True)
fig.suptitle("Figure 4. Small probability-score gains need uncertainty and an independent test\nSaved descriptive 95% month-block intervals; six blocks per final cohort, 34 for reruns",fontsize=15,fontweight="bold")
finish(fig,"JEV_STUDY_04_UNCERTAINTY.png")

# Evidence JSON deliberately contains exact numeric inputs for every figure.
DATA["figure_files"]=FILES
DATA["latest_labeled_class_counts"]=dict(actual_counts)
(STAGE/"JEV_STUDY_EVIDENCE.json").write_text(json.dumps(DATA,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("GENERATED",FILES)
print("EVIDENCE",str(STAGE/"JEV_STUDY_EVIDENCE.json"))
