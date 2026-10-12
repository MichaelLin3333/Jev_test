"""CLI bridge between the versioned news archive and the Jev workflow."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from .jev_analysis import FixtureJevClient, analyze, load_fixture, prepare_events, seed_fixture
from .jev_client import LiveJevClient
from .jev_report import render_report
from .model import parse_time, stamp, utc_now


def add_parser(subparsers):
    parser = subparsers.add_parser("jev-demo", help="Run an evidence-linked company interpretation demo")
    parser.add_argument("--backend", choices=("fixture", "live"), default="fixture",
        help="fixture is scripted/offline; live calls the paid Jev API using TYPESAFE_API_KEY")
    parser.add_argument("--data", help="Existing archive; omit to seed the synthetic Jev scenarios")
    parser.add_argument("--profile", help="Dated company exposure JSON; required for a real archive")
    parser.add_argument("--as-of", help="Input cutoff; default is the fixture cutoff, or now for --data")
    parser.add_argument("--output-root", default="reports/jev", help="Parent of a new, unique report directory")
    parser.add_argument("--max-calls", type=int, default=30, help="Live request attempt budget")
    parser.add_argument("--timeout", type=float, default=30, help="Seconds per live API call")


def run(args, open_existing):
    fixture = load_fixture()
    cutoff = stamp(parse_time(args.as_of)) if args.as_of else stamp(parse_time(fixture["default_cutoff"])) if not args.data else stamp(utc_now())
    profile = json.loads(Path(args.profile).read_text(encoding="utf-8-sig")) if args.profile else fixture["profile"]
    directory = Path(args.data or "jev-demo-data").resolve()
    output_root = Path(args.output_root).resolve()
    if output_root == directory or directory in output_root.parents:
        raise ValueError("Keep Jev reports outside the preserved news archive")
    if not args.data:
        seed_fixture(directory, fixture)
    archive = open_existing(directory)
    try:
        documents = list(archive.snapshot(cutoff))
        events = prepare_events(documents, profile, cutoff, archive.mode)
        if not events:
            raise ValueError("No observed documents at this cutoff; no Jev calls were made")
        if args.backend == "fixture":
            if any(f"{e['event_id']}:{e['revision']}" not in fixture["scripted_answers"] for e in events):
                raise ValueError("Scripted fixtures cover only the supplied scenarios; use --backend live for other news")
            backend = FixtureJevClient(fixture)
        else:
            backend = LiveJevClient(max_calls=args.max_calls, timeout=args.timeout)
        run_directory = output_root / (utc_now().strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:10])
        report = analyze(events, profile, cutoff, backend, args.backend, run_directory, archive.mode)
        output = render_report(report, run_directory)
        print("Scripted offline distributions; no model invoked." if args.backend == "fixture" else "Actual Jev API results; predictive accuracy unvalidated.")
        unit = "unique active events" if all(e["grouping"] == "supplied_synthetic_event_ids" for e in events) else "document candidates (cross-publisher clustering not performed)"
        print(f"{len(events)} {unit}; {backend.calls} evaluation call(s).")
        print(f"Combined economic evidence: {report['combined']['economic_balance']}; stock-return forecast: not estimated.")
        print(f"Report: {output}")
        return 0
    finally:
        archive.close()
