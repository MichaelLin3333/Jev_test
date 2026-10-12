from __future__ import annotations

import os
from datetime import timedelta
from urllib.parse import urlencode

from .http import FetchError
from .model import digest, gdelt_document, parse_time, sec_documents, stable_json, stamp


class CoverageError(RuntimeError):
    pass


def gdelt_window(client, archive, query, start, end, *, cap=250, minimum_seconds=900):
    url = "https://api.gdeltproject.org/api/v2/doc/doc?" + urlencode({
        "query": query["query"], "mode": "artlist", "format": "json",
        "sort": "datedesc", "maxrecords": cap,
        "startdatetime": start.strftime("%Y%m%d%H%M%S"),
        "enddatetime": end.strftime("%Y%m%d%H%M%S"),
    })
    response = client.get("gdelt", query["id"], url)
    if not isinstance(response.payload, dict) or not isinstance(response.payload.get("articles"), list):
        raise CoverageError("GDELT did not return an articles array")
    articles = response.payload["articles"]
    count, invalid = 0, 0
    for article in articles:
        try:
            normalized = gdelt_document(article)
            archive.ingest(normalized, response.request_id, query["id"], response.observed_at)
            count += 1
        except (KeyError, TypeError, ValueError):
            invalid += 1
    if invalid:
        raise CoverageError(f"{invalid} malformed article(s); valid articles were retained")
    if len(articles) >= cap:
        if (end - start).total_seconds() < minimum_seconds * 2:
            raise CoverageError("Result cap reached at minimum window; coverage is incomplete")
        midpoint = start + timedelta(seconds=int((end - start).total_seconds() // 2))
        # Shared boundary is intentional; the archive deduplicates it.
        gdelt_window(client, archive, query, start, midpoint, cap=cap,
                     minimum_seconds=minimum_seconds)
        gdelt_window(client, archive, query, midpoint, end, cap=cap,
                     minimum_seconds=minimum_seconds)
    return count


def validate_config(config):
    if not isinstance(config, dict):
        raise ValueError("Config must be a JSON object")
    queries = config.get("gdelt", {}).get("queries", [])
    ids = set()
    for query in queries:
        if not isinstance(query.get("id"), str) or not query["id"].strip():
            raise ValueError("Every GDELT query needs a nonempty id")
        if query["id"] in ids:
            raise ValueError("GDELT query ids must be unique")
        ids.add(query["id"])
        if not isinstance(query.get("query"), str) or not query["query"].strip():
            raise ValueError("Every GDELT query needs query text")
    for company in config.get("companies", []):
        if not company.get("ticker") or not company.get("name"):
            raise ValueError("Company ticker and name are required")
        cik = str(company.get("cik", ""))
        if not cik.isdigit() or not 1 <= len(cik) <= 10:
            raise ValueError("Company CIK must have 1–10 digits")
    overlap = config.get("collection", {}).get("overlap_minutes", 60)
    if not isinstance(overlap, (int, float)) or overlap < 15:
        raise ValueError("overlap_minutes must be at least 15")
    return config


def collect(config, archive, client, run_id, end, *, sources=("gdelt", "sec"),
            query_id=None, lookback_hours=None):
    settings = config.get("collection", {})
    initial_hours = (settings.get("initial_lookback_hours", 24)
                     if lookback_hours is None else lookback_hours)
    if not 0.25 <= initial_hours <= 24 * 89:
        raise ValueError("lookback_hours must be between 0.25 and 2136")
    overlap = timedelta(minutes=settings.get("overlap_minutes", 60))
    results = []

    def execute(provider, discovery_id, signature, operation):
        key = provider + ":" + discovery_id + ":" + digest(stable_json(signature))[:16]
        previous = archive.checkpoint(key)
        start = end - timedelta(hours=initial_hours)
        if previous and lookback_hours is None:
            start = parse_time(previous) - overlap
        # SEC/GDELT archive ends must not move into the future after clock changes.
        if start >= end:
            start = end - overlap
        count = 0
        status, detail = "ok", None
        try:
            count = operation(start, end)
        except (FetchError, CoverageError, KeyError, TypeError, ValueError) as error:
            status, detail = "partial", str(error)
        count = archive.query_count(run_id, provider, discovery_id)
        archive.query_result(run_id, provider, discovery_id, stamp(start), stamp(end),
                             status, count, detail, key)
        results.append({"provider": provider, "discovery_id": discovery_id,
                        "status": status, "normalized_count": count, "detail": detail})
        print(f"{provider} / {discovery_id}: {status}" + (f" — {detail}" if detail else ""),
              flush=True)

    if "gdelt" in sources and config.get("gdelt", {}).get("enabled", True):
        queries = config.get("gdelt", {}).get("queries", [])
        if query_id:
            queries = [query for query in queries if query["id"] == query_id]
            if not queries:
                raise ValueError(f"Unknown GDELT query id: {query_id}")
        for query in queries:
            execute("gdelt", query["id"], query["query"],
                    lambda start, end, q=query: gdelt_window(client, archive, q, start, end))

    if "sec" in sources and config.get("sec", {}).get("enabled", True):
        sec = config.get("sec", {})
        user_agent = os.environ.get(sec.get("user_agent_env", "SEC_USER_AGENT"), "").strip()
        forms = sec.get("forms", ["8-K", "10-K", "10-Q"])
        for company in config.get("companies", []):
            def fetch_company(start, end, company=company):
                if not user_agent or "@" not in user_agent:
                    raise CoverageError("Set SEC_USER_AGENT to a project name and your contact email")
                url = f"https://data.sec.gov/submissions/CIK{str(company['cik']).zfill(10)}.json"
                response = client.get("sec", company["ticker"], url, {"User-Agent": user_agent})
                documents = sec_documents(response.payload, company, forms, start, end)
                for document in documents:
                    archive.ingest(document, response.request_id, company["ticker"],
                                   response.observed_at)
                dates = response.payload["filings"]["recent"]["filingDate"]
                if dates and min(dates) > start.date().isoformat():
                    raise CoverageError("Requested history predates SEC recent filings; old files not fetched")
                return len(documents)
            execute("sec", company["ticker"], {"cik": company["cik"], "forms": forms},
                    fetch_company)
    if not results:
        raise ValueError("No enabled queries or companies selected")
    return results
