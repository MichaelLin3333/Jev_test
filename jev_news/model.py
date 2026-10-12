from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

UTC = timezone.utc


def utc_now() -> datetime:
    return datetime.now(UTC)


def stamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("A timestamp must include its timezone")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    """Require explicit timezone; never turn an unknown date into midnight."""
    value = value.strip()
    if len(value) == 16 and value[8] == "T" and value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp has no timezone: {value}")
    return parsed.astimezone(UTC)


def stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_url(value: str) -> str:
    parts = urlsplit(value.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("Expected an absolute HTTP(S) document URL")
    if parts.username or parts.password:
        raise ValueError("Document URLs must not contain credentials")
    # Preserve meaningful query order and path; remove known tracking only.
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_")
             and k.lower() not in {"fbclid", "gclid", "msclkid"}]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(),
                       parts.path or "/", urlencode(query), ""))


def gdelt_document(article: dict) -> dict:
    url = canonical_url(article["url"])
    title = article["title"].strip()
    if not title:
        raise ValueError("Empty GDELT title")
    seen = article.get("seendate")
    return {
        "provider": "gdelt", "provider_key": url, "url": url,
        "title": title, "text_type": "headline", "text": title,
        "published_at": None,  # seendate is discovery time, not publication time.
        "provider_seen_at": stamp(parse_time(seen)) if seen else None,
        "metadata": {
            "domain": article.get("domain") or urlsplit(url).hostname,
            "language": article.get("language"),
            "source_country": article.get("sourcecountry"),
        },
    }


def sec_documents(payload: dict, company: dict, forms: list[str],
                  start: datetime, end: datetime) -> list[dict]:
    if int(payload["cik"]) != int(company["cik"]):
        raise ValueError("SEC response CIK does not match requested company")
    recent = payload["filings"]["recent"]
    if not isinstance(recent, dict):
        raise ValueError("SEC filings.recent must be an object")
    required = ("accessionNumber", "form", "filingDate", "primaryDocument")
    size = len(recent.get("accessionNumber", []))
    for key in required:
        if not isinstance(recent.get(key), list) or len(recent[key]) != size:
            raise ValueError(f"SEC array missing or inconsistent: {key}")
    accepted = recent.get("acceptanceDateTime")
    if accepted is not None and (not isinstance(accepted, list) or len(accepted) != size):
        raise ValueError("Inconsistent SEC acceptance timestamps")
    results = []
    for index in range(size):
        form = recent["form"][index]
        if form not in forms:
            continue
        filing_date = recent["filingDate"][index]
        acceptance = accepted[index] if accepted else None
        published = parse_time(acceptance) if acceptance else None
        if published is not None:
            if not start <= published <= end:
                continue
        elif not start.date().isoformat() <= filing_date <= end.date().isoformat():
            continue
        accession = recent["accessionNumber"][index]
        document = recent["primaryDocument"][index]
        cik = str(int(company["cik"]))
        # Filenames originate in the SEC response. Reject path traversal.
        if not accession or not accession.replace("-", "").isdigit():
            raise ValueError("Invalid SEC accession number")
        if not document or "/" in document or "\\" in document or document in {".", ".."}:
            raise ValueError("Invalid SEC primary document filename")
        from urllib.parse import quote
        url = (f"https://www.sec.gov/Archives/edgar/data/{cik}/"
               f"{accession.replace('-', '')}/{quote(document, safe='.-_')}")
        title = f"{company['name']} {form} filed {filing_date}"
        results.append({
            "provider": "sec", "provider_key": f"{cik}:{accession}", "url": url,
            "title": title, "text_type": "filing_metadata", "text": None,
            "published_at": stamp(published) if published else None,
            "provider_seen_at": None,
            "metadata": {
                "ticker": company["ticker"], "cik": cik, "form": form,
                "accession_number": accession, "filing_date": filing_date,
                "timestamp_precision": "timestamp" if published else "date",
                "primary_document": document,
            },
        })
    return results
