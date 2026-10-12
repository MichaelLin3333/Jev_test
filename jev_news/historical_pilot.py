"""Small curated historical replay. Outcomes never enter model requests."""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import uuid
from decimal import Decimal
from pathlib import Path

from .jev_analysis import GATE, REGISTRY_VERSION, STAGES, analyze
from .jev_client import JevClientError, LiveJevClient, _http_transport
from .model import digest, parse_time, stable_json, stamp, utc_now

PRICE_PER_MILLION = 0.042
MAX_INPUT_TOKENS = 64_000
CALL_CAP = 33
MAX_BUDGET = 0.10
ROOT = Path(__file__).resolve().parent.parent


def load_corpus():
    inputs = json.loads((ROOT / "fixtures/historical-pilot-inputs.json").read_text(encoding="utf-8"))
    labels = json.loads((ROOT / "fixtures/historical-pilot-labels.json").read_text(encoding="utf-8"))
    return inputs, {c["case_id"]: c for c in labels["cases"]}


def anonymize(value, company_id):
    replacements = {
        "nvda": {"NVIDIA": "AsterCompute", "NVDA": "ACMP"},
        "meta": {"Meta Platforms": "BridgeNetwork", "Meta": "BridgeNetwork", "FB": "BNET",
            "Facebook": "SocialOne", "Instagram": "PhotoOne", "Messenger": "ChatOne",
            "WhatsApp": "ChatTwo", "Reels": "Clips"},
        "aapl": {"Apple": "CedarDevices", "AAPL": "CDEV", "iPhone": "HandsetOne",
            "Greater China": "Region East", "Chinese": "Region East", "China": "Region East"},
    }
    result = value
    for old, new in replacements[company_id].items():
        result = result.replace(old, new)
    return re.sub(r"\b(?:19|20)\d{2}\b", "Year X", result)


def build_cases(inputs, labels):
    cases = []
    for original in inputs["cases"]:
        prefix = original["id"].split("-")[0]
        base = copy.deepcopy(original)
        base["arm"] = "historical"
        base["base_id"] = original["id"]
        base["expected"] = labels[original["id"]]["expected"]
        if prefix == "aapl":
            # Exposure profile must remain meaningful under either event direction.
            base["profile"]["text"] = "Apple sells iPhone hardware and services and has exposure to consumer demand in Greater China."
        cases.append(base)
        masked = copy.deepcopy(base)
        masked["id"] = "anonymous-" + prefix
        masked["arm"] = "anonymous"
        for field in ("company", "ticker", "text", "claim_quote"):
            masked[field] = anonymize(masked[field], prefix)
        masked["profile"]["text"] = anonymize(masked["profile"]["text"], prefix)
        cases.append(masked)
        counter = copy.deepcopy(masked)
        counter["id"] = "counterfactual-" + prefix
        counter["arm"] = "counterfactual"
        counter["expected"] = {**counter["expected"], "revenue": "adverse" if base["expected"]["revenue"] == "favorable" else "favorable"}
        counter["text"] = {
            "nvda": "AsterCompute projected revenue of $5.50 billion, plus or minus 2%, for the next fiscal quarter after reporting $7.19 billion in the prior quarter. Management described decreasing demand for accelerated-computing and generative-AI products and said it was cutting production plans.",
            "meta": "BridgeNetwork projected next-quarter revenue of $35-37 billion and described stronger advertiser demand and improving monetization. Fourth-quarter operating margin fell to 37% from 46% a year earlier.",
            "aapl": "CedarDevices increased its fiscal Q1 revenue estimate to approximately $94 billion, above the earlier $89-93 billion range. Management attributed the improvement to stronger-than-expected HandsetOne sales, mainly in Region East, and more upgrades in some developed markets.",
        }[prefix]
        counter["claim_quote"] = counter["text"].split(". ")[0] + "." if prefix != "nvda" else counter["text"].split(" Management")[0]
        cases.append(counter)
    control = copy.deepcopy(cases[1])
    control.update(id="control-metadata", arm="control", text="", claim_quote=None,
        text_type="filing_metadata", expected={"disposition": "insufficient_evidence"})
    cases.append(control)
    unrelated = copy.deepcopy(cases[1])
    unrelated.update(id="control-unrelated", arm="control",
        text="A local park opened a pedestrian path. No technology company, commercial supplier, customer or economic policy is involved.",
        claim_quote="A local park opened a pedestrian path.", expected={"disposition": "unrelated"})
    cases.append(unrelated)
    return cases


def case_event(case, reconstructed_at):
    if parse_time(case["profile"]["as_of"]) > parse_time(case["evidence_time"]):
        raise ValueError("Profile facts postdate the reconstructed historical information cutoff")
    if case["claim_quote"] and case["claim_quote"] not in case["text"]:
        raise ValueError("Case claim quote is not grounded in the curated text")
    profile = {"ticker": case["ticker"], "name": case["company"], "synthetic": case["arm"] in {"counterfactual", "control"},
        "available_at": stamp(parse_time(case["profile"]["as_of"])),
        "evidence": [{"id": "exposure-1", "quote": case["profile"]["text"],
            "source_url": case["profile"]["source_urls"][0],
            "available_at": stamp(parse_time(case["profile"]["as_of"]))}]}
    event = {"event_id": case["id"], "revision": 1, "title": "Supplied announcement" if case["arm"] != "control" else "Supplied control",
        "text_type": case.get("text_type", "curated_paraphrase"), "text": case["text"],
        "claim_quote": case["claim_quote"], "assertion_status": "synthetic_counterfactual" if case["arm"] == "counterfactual" else "issuer_assertion",
        "evidence": [{"document_id": digest(case["id"]), "version_id": digest(case["text"]),
            "url": case["source_urls"][0], "text": case["text"], "observed_at": reconstructed_at,
            "raw_response_path": "curated-inputs.json", "content_hash": digest(case["text"])}],
        "source_lineages": ["supplied-issuer-summary"], "superseded_evidence": [],
        "comparison": {"status": "unknown", "market_consensus": "not_supplied"},
        "grouping": "single_curated_claim", "historical_information_cutoff": case["evidence_time"]}
    return event, profile


def model_state(state, anonymous=False):
    """Strip audit IDs, URLs and clocks from all prompts; mask dates in paired arms."""
    event = state["event"]
    clean = {"task": "Interpret only the supplied company economics before any subsequent market reaction.",
        "company_profile": {"name": state["company_profile"]["name"],
            "ticker": state["company_profile"]["ticker"],
            "evidence": [{"quote": e["quote"]} for e in state["company_profile"]["evidence"]]},
        "event": {key: event[key] for key in ("text_type", "text", "claim_quote", "assertion_status")}}
    if not anonymous:
        clean["historical_information_cutoff"] = event["historical_information_cutoff"]
    if "prior_stage_answers" in state:
        clean["prior_stage_answers"] = state["prior_stage_answers"]
    return clean


def direction_rule(text):
    """Deliberately simple economic-word baseline; not sentiment or a price model."""
    text = text.lower()
    negative = any(word in text for word in ("reduced", "decreasing demand", "headwinds", "weaker-than-expected"))
    positive = any(word in text for word in ("increased", "increasing demand", "stronger advertiser", "stronger-than-expected"))
    return "mixed" if positive and negative else "adverse" if negative else "favorable" if positive else "unknown"


class BudgetedClient:
    def __init__(self, client, budget, starting_calls=0, input_tokens=0, output_tokens=0):
        self.client = client
        self.model = client.model
        self.budget = budget
        self.starting_calls = starting_calls
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    @property
    def calls(self):
        return self.starting_calls + self.client.calls

    def evaluate(self, state, questions):
        ceiling = Decimal(self.calls + 1) * MAX_INPUT_TOKENS * Decimal(str(PRICE_PER_MILLION)) / 1_000_000
        if ceiling > Decimal(str(self.budget)):
            raise ValueError("Pilot token-cost reservation exhausted; no request sent")
        response = self.client.evaluate(state, questions)
        self.input_tokens += response["usage"]["input_tokens"]
        self.output_tokens += response["usage"]["output_tokens"]
        return response


def read_key(from_stdin=False):
    if from_stdin:
        # Never echo a credential through a terminal or save it to disk.
        if sys.stdin.isatty():
            import getpass
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                key = getpass.getpass("Jev API key (hidden): ").strip()
        else:
            key = sys.stdin.readline().strip()
        if not key:
            raise ValueError("No key received on standard input")
        return key
    key = os.environ.get("TYPESAFE_API_KEY")
    if key:
        return key
    if os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as handle:
                key, _ = winreg.QueryValueEx(handle, "TYPESAFE_API_KEY")
            if key:
                return key
        except OSError:
            pass
    raise ValueError("TYPESAFE_API_KEY is unavailable in this process or Windows user environment")


def summarize(case, report, label):
    item = report["events"][0]
    routing = item["stages"][0]["answers"]
    channels = next((s["answers"] for s in item["stages"] if s["stage"] == "channels"), {})
    observed = channels.get("revenue", {}).get("choice", "not_evaluated")
    expected = case["expected"]
    if case["arm"] == "control":
        matched = item["disposition"] == expected["disposition"]
    else:
        matched = observed == expected["revenue"]
    return {"case_id": case["id"], "base_id": case["base_id"], "arm": case["arm"],
        "company": case["company"], "expected": expected, "observed_revenue": observed,
        "revenue_probabilities": channels.get("revenue", {}).get("probabilities"),
        "matched": matched, "disposition": item["disposition"], "routing": routing,
        "other_channels": {k: channels[k]["choice"] for k in ("margin", "discount_rate") if k in channels},
        "economic_balance": report["combined"]["economic_balance"],
        "word_rule_revenue": direction_rule(case["text"]),
        "next_session": label["next_session"] if case["arm"] == "historical" else None}


def write_summary(directory, summary):
    (directory / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = summary["results"]
    substantive = [row for row in rows if row["arm"] != "control"]
    unsupported_rate = sum(row["other_channels"].get("discount_rate") not in {None, "unknown"} for row in substantive)
    lines = ["# Jev historical feasibility pilot", "", f"Status: **{summary['status']}**. Model: `{summary['model']}`.", "",
        "This is a curated economic-interpretation replay, not a point-in-time news backtest or a validated return forecast.", "",
        f"API attempts: {summary['api_attempts']}. Reported input tokens: {summary['input_tokens']:,}. "
        f"Estimated token cost: **${summary['estimated_cost_usd']:.6f}** at the published ${PRICE_PER_MILLION}/million input-token rate.", "",
        "| Case | Arm | Expected revenue channel | Jev revenue channel | Pass |", "| --- | --- | --- | --- | --- |"]
    for row in rows:
        expected = row["expected"].get("revenue", row["expected"].get("disposition"))
        observed = row["observed_revenue"] if row["arm"] != "control" else row["disposition"]
        lines.append(f"| {row['case_id']} | {row['arm']} | {expected} | {observed} | {'yes' if row['matched'] else 'no'} |")
    lines += ["", "## Aggregate results", ""]
    for arm in ("historical", "anonymous", "counterfactual", "control"):
        subset = [row for row in rows if row["arm"] == arm]
        lines.append(f"- {arm}: {sum(row['matched'] for row in subset)}/{len(subset)} matched the frozen endpoint.")
    unmetered = summary.get("unmetered_failed_attempts", 0)
    if unmetered:
        upper = summary["estimated_cost_usd"] + unmetered * MAX_INPUT_TOKENS * PRICE_PER_MILLION / 1_000_000
        lines += ["", f"{unmetered} failed response(s) lacked usable token accounting. Including a maximum-context allowance for those attempts gives a conservative published-price total below ${upper:.6f}. This is not an account billing statement."]
    lines += ["", "## Historical reaction context — evaluation only", "",
        "| Company | Next session | Reported stock return | S&P 500 |", "| --- | --- | --- | --- |"]
    for row in rows:
        outcome = row["next_session"]
        if outcome:
            lines.append(f"| {row['company']} | {outcome['date']} | [{outcome['return_pct_reported']:+g}%]({outcome['source_url']}) | {outcome['benchmark']['return_pct_reported']:+g}% |")
    lines += ["", "## Interpretation", "",
        "Semantic labels were frozen before inference, but the researcher knew these famous outcomes. The inputs are short issuer-based paraphrases; extraction, news selection and full-stream routing were bypassed.", "",
        "Anonymized inputs remove names, tickers, products, calendar years, source URLs and audit IDs from the actual model state. Recognizable financial figures can still reveal a famous event. Counterfactuals are coherent synthetic direction reversals, not historical reports.", "",
        "A majority-adverse baseline gets 2/3 on the selected historical revenue labels. The simple economic-word rule is reported alongside Jev. Success on obvious announcements does not establish an advantage over either baseline.", "",
        f"Exploratory audit found non-unknown discount-rate directions in {unsupported_rate} of {len(substantive)} substantive cases even though the supplied text contains no direct policy-rate, yield, financing-cost or risk-premium evidence. The current channel prompt needs a separate evidence gate. Materiality interpretation also needs a precisely defined numerical denominator.", "",
        "The next-session returns are rounded values from contemporary Reuters reporting. They include the overnight reaction and other market influences. They were not sent to Jev and are not returns earned by this system.", "",
        "Next evaluation: a frozen chronological sample of consecutive announcements, small/ambiguous/no-change cases, dated market expectations, market-adjusted outcomes and a prospective shadow run.", "",
        "[Official pricing](https://docs.typesafe.ai/models). Frozen protocol: `protocol.json`. Full inputs/labels are separate; each case directory preserves exact transmitted requests and validated responses."]
    (directory / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Make actual paid Jev API calls; otherwise freeze a dry-run protocol")
    parser.add_argument("--key-stdin", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--output-root", default="reports/historical-pilot")
    parser.add_argument("--max-calls", type=int, default=CALL_CAP)
    parser.add_argument("--budget-usd", type=float, default=MAX_BUDGET)
    parser.add_argument("--continue-from", help="Reuse completed results from a stopped pilot; keep the original total attempt cap")
    args = parser.parse_args(argv)
    if not 1 <= args.max_calls <= CALL_CAP or not 0 < args.budget_usd <= MAX_BUDGET:
        parser.error("Pilot is limited to 33 attempts and at most $0.10 at published token pricing")
    inputs, labels = load_corpus()
    cases = build_cases(inputs, labels)
    previous = None
    if args.continue_from:
        previous = json.loads((Path(args.continue_from) / "summary.json").read_text(encoding="utf-8"))
        if (previous["protocol"]["input_hash"] != digest(stable_json(cases))
                or previous["protocol"]["question_registry_hash"] != digest(stable_json(STAGES))
                or previous["protocol"]["label_hash"] != digest(stable_json(labels))):
            raise ValueError("Continuation inputs or question registry differ from the frozen pilot")
    reconstructed_at = stamp(utc_now())
    for case in cases:
        case_event(case, reconstructed_at)
    directory = Path(args.output_root).resolve() / (utc_now().strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:10])
    directory.mkdir(parents=True, exist_ok=False)
    protocol = {"version": "historical-feasibility-0.1.0", "registry_version": REGISTRY_VERSION,
        "frozen_at": reconstructed_at, "model": "jev-1.13.0", "cases": [{"id": c["id"], "arm": c["arm"], "expected": c["expected"]} for c in cases],
        "primary_endpoint": "revenue-channel agreement with researcher semantic labels",
        "secondary_endpoints": ["anonymous label preservation", "counterfactual reversal", "control rejection"],
        "not_evaluated": ["future return probabilities", "trading profitability", "causal attribution", "full news-stream selection"],
        "max_calls": args.max_calls, "budget_usd": args.budget_usd, "price_per_million_input_tokens": PRICE_PER_MILLION,
        "worst_case_token_cost_usd": args.max_calls * MAX_INPUT_TOKENS * PRICE_PER_MILLION / 1_000_000,
        "question_registry_hash": digest(stable_json(STAGES)), "input_hash": digest(stable_json(cases)),
        "label_hash": digest(stable_json(labels)), "source_availability": inputs["availability"]}
    if previous:
        protocol["continued_from"] = str(Path(args.continue_from).resolve())
        protocol["prior_attempts"] = previous["api_attempts"]
    (directory / "protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    (directory / "curated-inputs.json").write_text(json.dumps([{k: v for k, v in c.items() if k != "expected"} for c in cases], indent=2), encoding="utf-8")
    (directory / "evaluation-labels.json").write_text(json.dumps(labels, indent=2), encoding="utf-8")
    summary = {"status": "dry_run", "model": protocol["model"], "results": [], "api_attempts": 0,
        "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0, "protocol": protocol}
    if previous:
        summary.update(results=previous["results"], api_attempts=previous["api_attempts"],
            input_tokens=previous["input_tokens"], output_tokens=previous["output_tokens"],
            estimated_cost_usd=previous["estimated_cost_usd"],
            unmetered_failed_attempts=previous.get("unmetered_failed_attempts", 0) + (1 if previous["status"] == "failed" else 0))
    if not args.live:
        write_summary(directory, summary)
        print(f"Frozen dry-run protocol for {len(cases)} cases; no API calls. {directory}")
        return 0
    backend = None
    try:
        key = read_key(args.key_stdin)
        starting_calls = summary["api_attempts"]
        if starting_calls >= args.max_calls:
            raise ValueError("Original pilot attempt cap already exhausted")
        raw_directory = directory / "raw-model-responses"
        raw_directory.mkdir()

        def capture_transport(body, headers, timeout):
            response = _http_transport(body, headers, timeout)
            # Capture parsed provider JSON before validation, without credentials.
            path = raw_directory / f"{backend.calls:03d}.json"
            path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
            return response

        backend = BudgetedClient(LiveJevClient(api_key=key, max_calls=args.max_calls - starting_calls, timeout=30,
            transport=capture_transport), args.budget_usd, starting_calls, summary["input_tokens"], summary["output_tokens"])
        del key
        for case in cases:
            if case["id"] in {r["case_id"] for r in summary["results"]}:
                continue
            event, profile = case_event(case, reconstructed_at)
            report = analyze([event], profile, reconstructed_at, backend, "live", directory / case["id"],
                "historical_reconstruction", state_transform=lambda s, masked=case["arm"] != "historical": model_state(s, masked))
            summary["results"].append(summarize(case, report, labels[case["base_id"]]))
            print(f"{case['id']}: {summary['results'][-1]['observed_revenue']} ({summary['results'][-1]['disposition']})", flush=True)
        summary["status"] = "complete"
    except (ValueError, OSError, JevClientError) as error:
        summary["status"] = "failed"
        summary["error"] = str(error)
        print(f"Pilot stopped: {error}", file=sys.stderr)
    finally:
        if backend:
            summary.update(api_attempts=backend.calls, input_tokens=backend.input_tokens, output_tokens=backend.output_tokens,
                estimated_cost_usd=backend.input_tokens * PRICE_PER_MILLION / 1_000_000)
        write_summary(directory, summary)
        print(f"Report: {directory / 'REPORT.md'}", flush=True)
        print(f"API attempts: {summary['api_attempts']}; estimated token cost: ${summary['estimated_cost_usd']:.6f}", flush=True)
    return 0 if summary["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
