"""Development-only reuse and a fresh, outcome-sealed 2026 article holdout."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib
import re
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from .core import ROOT, OLD, REPO, read, save, digest, now, protocol, fetch, preserve_snapshot, previous_data

def old_windows():
    result = defaultdict(list)
    for case in read(OLD / "data" / "cases.json"):
        result[case["company"]["ticker"]].append({"id": case["case_id"], "sessions": case["window"]["sessions"]})
    folder = REPO / "jev_model_eval" / "qualitative_news_tests_2026-10-17"
    for path in folder.glob("*.json"):
        if "previous_attempt" in path.name:
            continue
        times = set()
        def visit(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == "decision_time" and isinstance(item, str):
                        times.add(item)
                    if key not in ("response", "raw_response"):
                        visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)
        visit(read(path))
        for time in times:
            if "2022-01-01" <= time[:10] <= "2026-12-01":
                result["NVDA"].append({"id": path.stem, "sessions": previous_data.target_window(time)["sessions"]})
    return dict(result)

def archive_rows(ticker, url, html):
    if ticker not in ("META", "MSFT"):
        return previous_data.archive_rows(ticker, url, html)
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        pattern = r"about\.fb\.com/news/2026/\d\d/[^/]+/?$" if ticker == "META" else r"blogs\.microsoft\.com/blog/2026/\d\d/\d\d/[^/]+/?$"
        if not re.search(pattern, href) or len(anchor.get_text(" ", strip=True)) < 15:
            continue
        card = anchor.find_parent("article")
        tag = card.find("time") if card else None
        date = previous_data.parse_date(tag.get("datetime", tag.get_text(" ", strip=True))) if tag else None
        if not date:
            match = re.search(r"/(2026)/(\d\d)/(\d\d)/", href)
            date = "-".join(match.groups()) if match else None
        if date:
            rows.append({"ticker": ticker, "url": previous_data.canonical_url(href), "date": date, "title": anchor.get_text(" ", strip=True), "archive_url": url})
    return rows

def discover(ticker):
    patterns = {
        "NVDA": "https://nvidianews.nvidia.com/news?year=2026&page={page}",
        "AAPL": "https://www.apple.com/newsroom/archive/?page={page}",
        "AMD": "https://ir.amd.com/news-events/press-releases?year=2026&page={page}",
        "META": "https://about.fb.com/news/2026/page/{page}/",
        "MSFT": "https://blogs.microsoft.com/blog/2026/page/{page}/",
    }
    found = {}
    pages = []
    for page in range(1, 101):
        url = patterns[ticker].format(page=page)
        try:
            html, _ = fetch(url)
        except ValueError as error:
            pages.append({"url": url, "error": str(error)})
            break
        rows = archive_rows(ticker, url, html)
        new = sum(row["url"] not in found for row in rows)
        for row in rows:
            found[row["url"]] = row
        pages.append({"url": url, "rows": len(rows)})
        if not rows or (page > 1 and new == 0):
            break
        if min(row["date"] for row in rows) < "2026-01-01":
            break
    eligible = sorted((row for row in found.values() if "2026-01-01" <= row["date"] <= "2026-06-30"), key=lambda row: (row["date"], row["url"]))
    save(ROOT / "data" / "discovery" / (ticker + ".json"), {"pages": pages, "eligible": eligible})
    print("DISCOVER", ticker, len(eligible), "eligible 2026 articles", flush=True)
    return ticker, eligible

def prepare():
    destination = ROOT / "frozen" / "dataset.json"
    if destination.exists():
        print("Dataset already frozen; no collection changes", flush=True)
        return
    if not (ROOT / "frozen" / "protocol.json").exists():
        save(ROOT / "frozen" / "previous_files.json", preserve_snapshot())
        save(ROOT / "frozen" / "protocol.json", protocol())
    elif digest(protocol()) != digest(read(ROOT / "frozen" / "protocol.json")):
        raise ValueError("Protocol changed after preparation started")
    all_old = read(OLD / "data" / "cases.json")
    development = [case for case in all_old if case["split"] != "test"]
    assert len(development) == 120
    save(ROOT / "data" / "development_cases.json", development)
    outcomes = read(OLD / "data" / "development_outcomes.json")
    market = read(OLD / "data" / "development_market_features.json")
    assert set(outcomes) == {case["case_id"] for case in development}
    save(ROOT / "data" / "development_outcomes.json", outcomes)
    save(ROOT / "data" / "development_market.json", market)
    forbidden = old_windows()
    previous_urls = {previous_data.canonical_url(article["url"]) for case in all_old for article in case["articles"]}
    previous_hashes = {article["text_sha256"] for case in all_old for article in case["articles"]}
    selected = []
    rejected = []
    used_hashes = set(previous_hashes)
    blocked = {ticker: list(windows) for ticker, windows in forbidden.items()}
    def accept(ticker, row, control=False):
        cutoff = datetime.fromisoformat(row["date"] + "T23:59:59").replace(tzinfo=previous_data.ZoneInfo("America/New_York")).isoformat()
        window = previous_data.target_window(cutoff)
        conflicts = [item["id"] for item in blocked.get(ticker, []) if set(item["sessions"]) & set(window["sessions"])]
        if conflicts:
            raise ValueError("Same-stock target window overlaps prior/selected cases: " + ", ".join(conflicts))
        if previous_data.canonical_url(row["url"]) in previous_urls:
            raise ValueError("Previously inspected source URL")
        article = previous_data.article_text(row, control)
        if article["text_sha256"] in used_hashes:
            raise ValueError("Duplicate article text")
        article["text_kind"] = "publisher_excerpt"
        article["historical_version_uncertain"] = True
        if control:
            raw = BeautifulSoup((ROOT / article["raw_source_file"]).read_text(encoding="utf-8"), "html.parser")
            text = raw.title.get_text(" ", strip=True) if raw.title else ""
            date = datetime.fromisoformat(row["date"])
            dateline = str(date.year) + date.strftime("%B").lower() + str(date.day)
            if dateline not in re.sub(r"[^a-z0-9]", "", text.lower()):
                raise ValueError("NASA historical dateline mismatch")
        case = previous_data.case_from_article(ticker, "holdout", article, "round2-" + ticker + "-" + row["date"], control)
        case["case_id"] = "round2-" + case["case_id"]
        selected.append(case)
        used_hashes.add(article["text_sha256"])
        blocked.setdefault(ticker, []).append({"id": case["case_id"], "sessions": window["sessions"]})
        print("HOLDOUT INPUT", ticker, row["date"], "control" if control else "issuer", flush=True)
    # Apply exactly the same overlap rule to every source, including controls.
    for ticker, first in protocol()["holdout"]["controls"].items():
        for offset in range(15):
            date = (datetime.fromisoformat(first) + timedelta(days=offset)).date().isoformat()
            row = {"ticker": "NASA", "title": "NASA Astronomy Picture of the Day", "date": date, "url": "https://apod.nasa.gov/apod/ap" + datetime.fromisoformat(date).strftime("%y%m%d") + ".html"}
            try:
                accept(ticker, row, True)
                break
            except ValueError as error:
                rejected.append({**row, "target": ticker, "reason": str(error)})
    with ThreadPoolExecutor(max_workers=3) as pool:
        discovered = list(pool.map(discover, protocol()["holdout"]["universe"]))
    for ticker, rows in discovered:
        groups = []
        block = []
        start = None
        for row in rows:
            date = datetime.fromisoformat(row["date"])
            if start is None or (date - start).days > 7:
                if block:
                    groups.append(block)
                block = []
                start = date
            block.append(row)
        if block:
            groups.append(block)
        anchors = [min(group, key=lambda row: (previous_data.title_category(row), digest({"seed": 2718, "url": row["url"]}))) for group in groups]
        anchors.sort(key=lambda row: (row["date"], row["url"]))
        used = set()
        for j in range(5):
            center = (j + 0.5) * len(anchors) / 5 - 0.5
            if j == 0:
                order = sorted(range(len(anchors)), key=lambda i: (previous_data.title_category(anchors[i]) if previous_data.title_category(anchors[i]) <= 1 else 9, digest(anchors[i]["url"])))
            elif j == 1:
                order = sorted(range(len(anchors)), key=lambda i: (previous_data.title_category(anchors[i]) != 2, digest(anchors[i]["url"])))
            else:
                order = sorted(range(len(anchors)), key=lambda i: (abs(i-center), i))
            for i in order:
                if i in used:
                    continue
                used.add(i)
                try:
                    accept(ticker, anchors[i])
                    break
                except ValueError as error:
                    rejected.append({**anchors[i], "reason": str(error)})
    selected.sort(key=lambda case: (case["decision_time"], case["company"]["ticker"]))
    save(ROOT / "data" / "holdout_cases.json", selected)
    save(ROOT / "data" / "source_exclusions.json", rejected)
    if len(selected) != 30:
        raise ValueError("Expected 30 real holdout inputs, obtained " + str(len(selected)))
    save(destination, {"frozen_at": now(), "development_sha256": digest(development), "holdout_sha256": digest(selected), "protocol_sha256": digest(protocol()), "development_ids": [case["case_id"] for case in development], "holdout_ids": [case["case_id"] for case in selected], "prior_overlap_checks_include_controls": True, "holdout_outcomes_acquired": False, "old_label_code_sha256": hashlib.sha256((OLD / "data.py").read_bytes()).hexdigest(), "old_evaluator_sha256": hashlib.sha256((OLD / "evaluate.py").read_bytes()).hexdigest()})
    print("FROZEN: 120 development inputs and 30 fresh holdout inputs; holdout labels absent", flush=True)

def verify_dataset():
    frozen = read(ROOT / "frozen" / "dataset.json")
    assert digest(read(ROOT / "data" / "development_cases.json")) == frozen["development_sha256"]
    assert digest(read(ROOT / "data" / "holdout_cases.json")) == frozen["holdout_sha256"]
    assert digest(protocol()) == frozen["protocol_sha256"]
    assert hashlib.sha256((OLD / "data.py").read_bytes()).hexdigest() == frozen["old_label_code_sha256"]
    assert hashlib.sha256((OLD / "evaluate.py").read_bytes()).hexdigest() == frozen["old_evaluator_sha256"]
    return frozen

def acquire_holdout_outcomes():
    import yfinance as yf
    if not (ROOT / "frozen" / "selection.json").exists():
        raise ValueError("Cannot acquire holdout labels before selection")
    cases = read(ROOT / "data" / "holdout_cases.json")
    yf.set_tz_cache_location(str(ROOT / "data" / "yfinance_cache"))
    prices = {}
    for ticker in protocol()["holdout"]["universe"] + ["SPY"]:
        path = ROOT / "data" / "holdout_prices" / (ticker + ".json")
        if path.exists():
            prices[ticker] = read(path)["bars"]
            continue
        frame = yf.Ticker(ticker).history(start="2025-10-01", end="2026-07-15", auto_adjust=False, actions=True, repair=False, raise_errors=True)
        bars = [{"date": str(index.date()), "open": float(row["Open"]) if pd.notna(row["Open"]) else None, "close": float(row["Close"]) if pd.notna(row["Close"]) else None, "split": float(row.get("Stock Splits", 0)), "dividends": float(row.get("Dividends", 0))} for index, row in frame.iterrows()]
        if not bars:
            raise ValueError("No historical prices: " + ticker)
        save(path, {"retrieved_at": now(), "ticker": ticker, "source": "Yahoo/yfinance", "auto_adjust": False, "actions": True, "repair": False, "bars": bars})
        prices[ticker] = bars
    outcomes = {case["case_id"]: previous_data.label_case(case, prices[case["company"]["ticker"]]) for case in cases}
    market = {case["case_id"]: previous_data.market_features(case, prices[case["company"]["ticker"]], prices["SPY"]) for case in cases}
    save(ROOT / "data" / "holdout_outcomes.json", outcomes)
    save(ROOT / "data" / "holdout_market.json", market)
    return cases, outcomes, market
