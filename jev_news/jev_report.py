"""Self-contained, readable report; no scripts, fonts or services fetched."""
from __future__ import annotations

import html
import json
from pathlib import Path


def esc(value):
    return html.escape(str(value), quote=True)


def label(value):
    return str(value).replace("_", " ")


def render_report(report, directory):
    def answer_rows(stage):
        rows = []
        for name, answer in stage["answers"].items():
            kind = answer["type"]
            if kind == "noul":
                value = f"{answer['noul']:.0%} yes"
                detail = "Yes/no judgment; not a return probability."
            elif kind == "choice":
                value = label(answer["choice"])
                detail = " · ".join(f"{label(k)} {v:.0%}" for k, v in answer["probabilities"].items())
            else:
                value = f"{answer['score']:.2f} / {len(answer['legend']) - 1}"
                detail = "Ordinal exposure rubric; not a price change."
            rows.append(f'<div class="answer"><span>{esc(label(name))} <small>{esc(kind)}</small></span>'
                        f'<strong>{esc(value)}</strong><p>{esc(detail)}</p></div>')
        return "".join(rows)

    cards = []
    for event in report["events"]:
        disposition = event["disposition"]
        comparison = event["comparison"]
        baseline = "No comparable baseline supplied."
        if comparison["status"] != "unknown":
            relative = comparison["relative_change"]
            movement = f"{relative:+.0%}" if relative is not None else "percentage undefined"
            baseline = (f"Prior issuer plan: {comparison['prior']:g} → {comparison['current']:g} "
                f"{comparison['unit']} ({movement}). This is not market consensus or a sales forecast.")
        stages = "".join(f'<details><summary>{i}. {esc(label(s["stage"]))}</summary>'
            f'{answer_rows(s)}<a href="{esc(s["request_path"])}">Input and questions</a> · '
            f'<a href="{esc(s["response_path"])}">Response distribution</a></details>'
            for i, s in enumerate(event["stages"], 1))
        superseded = ""
        if event["superseded_evidence"]:
            superseded = '<details><summary>Superseded evidence</summary>' + "".join(
                f'<p>{esc(e["text"])}</p>' for e in event["superseded_evidence"]) + '</details>'
        evidence = "".join(f'<li><a href="{esc(e["url"])}">{esc(e["document_id"][:12])}</a>'
            f' · observed {esc(e["observed_at"])}<small>Version {esc(e["version_id"][:12])}</small></li>'
            for e in event["evidence"])
        cards.append(f'<article class="event" data-kind="{esc(disposition)}">'
            f'<div class="eyebrow">Revision {event["revision"]} · {len(event["evidence"])} active document(s)'
            f' · {len(event["source_lineages"])} source lineage(s)</div>'
            f'<h2>{esc(event["title"])}</h2><div class="tags"><span class="tag {esc(event["economic_direction"])}">'
            f'{esc(label(event["economic_direction"]))} channel</span><span class="tag">'
            f'{esc(label(disposition))}</span></div><p>{esc(event["reason"])}</p>'
            f'<blockquote>{esc(event["claim_quote"] or "No source passage supplied; filing metadata only.")}</blockquote>'
            f'<p class="baseline">{esc(baseline)}</p><div class="stages">{stages}</div>'
            f'<details><summary>Evidence and timing</summary><ul>{evidence}</ul>'
            f'<p>Grouping: {esc(label(event["grouping"]))}. '
            f'Assertion status: {esc(label(event["assertion_status"]))}.</p></details>{superseded}</article>')
    combined = report["combined"]
    grouped = all(e["grouping"] == "supplied_synthetic_event_ids" for e in report["events"])
    grouping_notice = ("Repeated synthetic documents do not multiply an event's effect. Event identities are supplied in the fixture."
        if grouped else "Document identity duplicates are removed; cross-publisher event clustering is not implemented. Counts represent document candidates.")
    fixture = report["backend"] == "fixture"
    mode = "SCRIPTED OFFLINE DEMO · NO MODEL INVOKED" if fixture else "LIVE JEV · UNVALIDATED ECONOMIC INTERPRETATION"
    data_notice = ("All events and company exposures are invented. These are not reports about NVIDIA or real market conditions."
        if report["synthetic_inputs"] else "Real archive inputs. Company exposures were supplied in a dated profile; feed completeness is not established.")
    counts = [("Favorable", len(combined["favorable_events"])), ("Adverse", len(combined["adverse_events"])),
              ("Rumors", len(combined["rumor_events"])), ("Insufficient", len(combined["insufficient_events"])),
              ("Unrelated", len(combined["unrelated_events"]))]
    metrics = "".join(f'<div><strong>{count}</strong><span>{name}</span></div>' for name, count in counts)
    exposures = "".join(f'<li>{esc(e["quote"])}</li>' for e in report["company"]["evidence"])
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Jev news interpretation demo</title><style>
:root {{color-scheme:light;--ink:#172b3b;--muted:#536573;--line:#dbe3e7;--paper:#fff;--bg:#f2f5f4;--accent:#0c655c}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:36px 24px 70px}}h1{{font-size:clamp(30px,4vw,48px);line-height:1.15;margin:14px 0}}
h2{{font-size:21px;line-height:1.35;margin:8px 0 16px}}p{{margin:12px 0}}a{{color:var(--accent)}}small{{display:block;color:var(--muted);font-size:12px}}
.eyebrow{{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}}.notice{{border-left:4px solid #a06512;background:#fff3d9;padding:14px 18px;margin:20px 0}}
.lead{{font-size:18px;max-width:820px}}.flow{{display:flex;gap:12px;flex-wrap:wrap;margin:25px 0}}.flow span{{padding:10px 15px;border:1px solid var(--line);background:var(--paper);border-radius:8px}}
.panel,.event{{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:24px;margin:20px 0}}.metrics{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:20px 0}}
.metrics div{{background:var(--bg);padding:15px;border-radius:8px}}.metrics strong{{display:block;font-size:28px}}.metrics span{{color:var(--muted);font-size:13px}}
.tags{{display:flex;gap:8px;flex-wrap:wrap}}.tag{{border-radius:20px;background:#edf1f4;font-size:12px;padding:5px 10px}}.favorable{{background:#dbf1e7;color:#205943}}.adverse{{background:#fbe2df;color:#813b32}}.mixed{{background:#f7ecd3;color:#72501f}}
blockquote{{margin:20px 0;padding:12px 18px;border-left:3px solid var(--accent);background:#f5f9f8}}.baseline{{color:var(--muted);font-size:14px}}
details{{border-top:1px solid var(--line);padding:12px 0}}summary{{cursor:pointer;font-weight:600}}.answer{{display:grid;grid-template-columns:1fr auto;gap:4px;padding:12px 0;border-bottom:1px solid #edf1f4}}
.answer p{{grid-column:1/-1;margin:0;color:var(--muted);font-size:13px}}.answer small{{display:inline;margin-left:7px}}li{{margin:8px 0}}footer{{color:var(--muted);font-size:13px}}
@media(max-width:600px){{main{{padding:20px 14px}}.panel,.event{{padding:18px}}.metrics{{grid-template-columns:repeat(3,1fr)}}.answer{{grid-template-columns:1fr}}}}
</style></head><body><main><div class="eyebrow">{esc(mode)}</div>
<h1>From news to company economics</h1><p class="lead">A small Jev decision workflow for {esc(report["company"]["name"])} ({esc(report["company"]["ticker"])}). Follow the evidence, routing and economic channels for each active event.</p>
<div class="notice">{esc(data_notice)} {'Every distribution is hand-authored to demonstrate the workflow.' if fixture else 'Distributions are model judgments; calibration and predictive accuracy have not been measured.'}</div>
<div class="flow"><span>Observed news snapshot</span><span>1. Claim + relevance</span><span>2. Economic channels</span><span>3. Exposure scale, when known</span><span>Combined evidence state</span></div>
<section class="panel"><div class="eyebrow">Combined company state</div><h2>{esc(label(combined["economic_balance"]))}</h2><div class="metrics">{metrics}</div>
<p>Favorable and adverse evidence remain separate. Rumors are isolated. {esc(grouping_notice)}</p>
<p><strong>Stock-return forecast: not estimated.</strong> No price target, return probabilities or trading signal is produced.</p>
<small>Input cutoff: {esc(report["input_cutoff"])} · Completed: {esc(report["completed_at"])}<br>This replay demonstrates available inputs; it is not a prospective market test.</small></section>
<details class="panel"><summary>Company exposure assumptions</summary><ul>{exposures}</ul></details>
{''.join(cards)}
<footer><p><a href="report.json">Complete machine-readable report</a> · <a href="inputs.json">Frozen inputs</a> · <a href="question-registry.json">Versioned questions</a></p>
<p>Registry {esc(report["registry_version"])} · {report["evaluation_calls"]} evaluation call(s) · No empirical calibration. Demo gate: {report["gate_threshold"]:.0%}.</p></footer>
</main></body></html>'''
    output = Path(directory) / "report.html"
    output.write_text(document, encoding="utf-8")
    return output
