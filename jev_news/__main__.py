from __future__ import annotations

import argparse
import json
import sys
import time
import sqlite3
from datetime import timedelta
from pathlib import Path

from .collect import collect, validate_config
from .http import HttpClient
from .model import gdelt_document, parse_time, sec_documents, stamp, utc_now
from .store import Archive
from .jev_client import JevClientError


def open_existing(directory):
    location = Path(directory) / "news.sqlite3"
    if not location.exists():
        raise ValueError(f"No archive found at {location}; run demo or collect first")
    connection = sqlite3.connect(location)
    try:
        row = connection.execute("SELECT value FROM settings WHERE key='mode'").fetchone()
    finally:
        connection.close()
    if not row:
        raise ValueError("Archive mode is missing")
    return Archive(directory, row[0])


def run_demo(directory):
    fixture_path = Path(__file__).resolve().parent.parent / "fixtures" / "demo.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    archive = Archive(directory, "synthetic")
    try:
        run_id = archive.start_run({"fixture": "demo.json", "synthetic": True},
                                   fixture["observed_times"][0])
        for index, payload in enumerate(fixture["gdelt_responses"]):
            observed = fixture["observed_times"][index]
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request_id = archive.record_request(
                run_id, "gdelt", "synthetic-demo", "fixture://gdelt",
                observed, observed, 200, raw)
            for article in payload["articles"]:
                document = gdelt_document(article)
                document["metadata"]["synthetic"] = True
                archive.ingest(document, request_id, "synthetic-demo", observed)
        observed = fixture["observed_times"][-1]
        payload = fixture["sec_response"]
        request_id = archive.record_request(
            run_id, "sec", "NVDA", "fixture://sec", observed, observed,
            200, json.dumps(payload).encode("utf-8"))
        for document in sec_documents(payload, fixture["company"], ["8-K"],
                                      parse_time(observed) - timedelta(days=1),
                                      parse_time(observed)):
            document["metadata"]["synthetic"] = True
            archive.ingest(document, request_id, "NVDA", observed)
        archive.finish_run(run_id, "ok")
        print(json.dumps(archive.status(), ensure_ascii=False, indent=2))
        print("Synthetic demo only. Re-running preserves content identity.")
    finally:
        archive.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Standalone, replayable news collection draft")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Create clearly synthetic sample data without network access")
    demo.add_argument("--data", default="demo-data")
    live = sub.add_parser("collect", help="Collect one batch, optionally repeat in foreground")
    live.add_argument("--config", default="config.example.json")
    live.add_argument("--data", default="data")
    live.add_argument("--sources", choices=("all", "gdelt", "sec"), default="all")
    live.add_argument("--query", help="Run one configured GDELT query")
    live.add_argument("--lookback-hours", type=float, help="Override checkpoint with an explicit lookback")
    live.add_argument("--max-requests", type=int, default=60)
    live.add_argument("--timeout", type=float, default=20)
    live.add_argument("--retries", type=int, default=2)
    live.add_argument("--watch", action="store_true", help="Repeat until Ctrl+C; keep this terminal running")
    live.add_argument("--interval-minutes", type=float, default=15)
    status = sub.add_parser("status", help="Inspect archive counts and latest collection gaps")
    status.add_argument("--data", default="data")
    export = sub.add_parser("export", help="Export one observed document version per URL/accession")
    export.add_argument("--data", default="data")
    export.add_argument("--as-of", help="UTC/offset timestamp; defaults to now")
    export.add_argument("--output", default="exports/news.jsonl")
    from .jev_demo import add_parser, run as run_jev_demo
    add_parser(sub)
    args = parser.parse_args(argv)
    archive = None
    try:
        if args.command == "jev-demo":
            return run_jev_demo(args, open_existing)
        if args.command == "demo":
            run_demo(args.data)
            return 0
        if args.command in {"status", "export"}:
            archive = open_existing(args.data)
            if args.command == "status":
                print(json.dumps(archive.status(), ensure_ascii=False, indent=2))
            else:
                cutoff = stamp(parse_time(args.as_of)) if args.as_of else stamp(utc_now())
                output = Path(args.output).resolve()
                # An export must never overwrite a database or preserved evidence.
                if output == (archive.directory / "news.sqlite3") or archive.directory / "raw" in output.parents:
                    raise ValueError("Export destination overlaps the database or raw archive")
                output.parent.mkdir(parents=True, exist_ok=True)
                count = 0
                with output.open("w", encoding="utf-8", newline="\n") as stream:
                    for document in archive.snapshot(cutoff):
                        stream.write(json.dumps(document, ensure_ascii=False) + "\n")
                        count += 1
                print(f"Exported {count} documents to {output} (as of {cutoff})")
            return 0
        config = validate_config(json.loads(Path(args.config).read_text(encoding="utf-8-sig")))
        if args.max_requests < 1 or args.timeout <= 0 or args.retries < 0:
            raise ValueError("Request budget and timeout must be positive; retries cannot be negative")
        if args.interval_minutes < 1:
            raise ValueError("Collection interval must be at least one minute")
        archive = Archive(args.data, "live")
        sources = ("gdelt", "sec") if args.sources == "all" else (args.sources,)
        while True:
            run_id = archive.start_run(config)
            result = "failed"
            try:
                client = HttpClient(archive, run_id, timeout=args.timeout, retries=args.retries,
                                    max_requests=args.max_requests)
                rows = collect(config, archive, client, run_id, utc_now(), sources=sources,
                               query_id=args.query, lookback_hours=args.lookback_hours)
                result = "ok" if all(row["status"] == "ok" for row in rows) else "partial"
            finally:
                archive.finish_run(run_id, result)
            print(f"Batch {result}; {client.used} HTTP attempt(s).", flush=True)
            if not args.watch:
                return 0 if result == "ok" else 2
            print(f"Next batch in {args.interval_minutes:g} minutes. Ctrl+C stops collection.", flush=True)
            time.sleep(args.interval_minutes * 60)
    except KeyboardInterrupt:
        print("\nCollection stopped.")
        return 130
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error, JevClientError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    finally:
        if archive:
            archive.close()


if __name__ == "__main__":
    raise SystemExit(main())
