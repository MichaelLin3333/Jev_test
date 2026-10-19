"""Discover primary-source articles, freeze cases, and obtain price-derived labels."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse
import re
import math
import hashlib
from decimal import Decimal
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import exchange_calendars as xcals
from .common import ROOT, REPO, now, read, save, digest, fetch, append, protocol, protection_manifest

CONTEXT={
 "NVDA":{"name":"NVIDIA","profile":"NVIDIA designs accelerated computing platforms, GPUs and related software used in data centers, AI, graphics and gaming.","source":"https://nvidianews.nvidia.com/"},
 "AAPL":{"name":"Apple","profile":"Apple develops and sells personal computing devices including iPhone, Mac and iPad, with operating systems and digital services.","source":"https://www.apple.com/newsroom/"},
 "AMD":{"name":"Advanced Micro Devices","profile":"AMD designs computing and graphics processors, including Ryzen, EPYC and Radeon products, serving PC, data-center, gaming and embedded markets.","source":"https://ir.amd.com/"},
 "META":{"name":"Meta Platforms","profile":"Meta operates Facebook, Instagram, WhatsApp and related social products; advertising is a major business activity. It also develops virtual and augmented reality products.","source":"https://about.fb.com/"},
 "MSFT":{"name":"Microsoft","profile":"Microsoft develops software and cloud services including Windows, Microsoft 365 and Azure, and operates gaming, business-software and related technology businesses.","source":"https://blogs.microsoft.com/"}
}
CAL=xcals.get_calendar("XNYS",start="2022-01-01",end="2026-12-31")

def parse_date(text):
    text=text.strip()
    if re.match(r"\d{4}-\d{2}-\d{2}",text): return text[:10]
    for fmt in ("%B %d, %Y","%b %d, %Y","%Y %B %d"):
        try: return datetime.strptime(text,fmt).date().isoformat()
        except ValueError: pass
    match=re.search(r"([A-Z][a-z]+ \d{1,2}, \d{4})",text)
    if match: return parse_date(match.group(1))
    return None

def canonical_url(url): return url.split("?")[0].split("#")[0].rstrip("/")

def title_category(row):
    title=row["title"].lower()
    if re.search(r"layoff|restructur|restrict|terminat|loss|declin|headwind|suspend|job cuts|efficiency",title):return 0
    if re.search(r"security|privacy|scam|fraud|misinformation|safety|disinformation|threat|regulat|risk",title):return 1
    if re.search(r"financial results|reports.*quarter|quarter.*results|earnings",title):return 2
    return 3

def archive_rows(ticker,url,html):
    soup=BeautifulSoup(html,"html.parser"); rows=[]
    if ticker=="NVDA":
        for card in soup.select(".index-item-wrapper"):
            a=card.select_one("h3 a");date=card.select_one(".index-item-text-info-date")
            if a and date: rows.append((a,parse_date(date.get_text(" ",strip=True))))
    elif ticker=="AAPL":
        for a in soup.select("a.result__item"):
            d=a.select_one(".item__date"); rows.append((a,parse_date(d.get_text(" ",strip=True)) if d else None))
    else:
        for a in soup.find_all("a",href=True):
            href=a["href"]
            if ticker=="AMD" and "/press-releases/detail/" not in href: continue
            if ticker=="META" and not re.search(r"about\.fb\.com/news/202[345]/\d\d/[^/]+/?$",href): continue
            if ticker=="MSFT" and not re.search(r"blogs\.microsoft\.com/blog/202[345]/\d\d/\d\d/[^/]+/?$",href): continue
            if len(a.get_text(" ",strip=True))<15: continue
            card=a.find_parent("article")
            time_tag=card.find("time") if card else None
            date=parse_date(time_tag.get("datetime",time_tag.get_text(" ",strip=True))) if time_tag else None
            if not date:
                m=re.search(r"/(202[345])/(\d\d)/(\d\d)/",href)
                if m: date="-".join(m.groups())
            rows.append((a,date))
    result=[]
    for a,date in rows:
        h=a.find(["h2","h3"])
        title=(h or a).get_text(" ",strip=True)
        if ticker=="AAPL":
            h=a.select_one(".item__headline");title=h.get_text(" ",strip=True) if h else title
        if date: result.append({"ticker":ticker,"url":canonical_url(urljoin(url,a.get("href",""))),"date":date,"title":title,"archive_url":url})
    return result

def discover_company(ticker):
    p=protocol();all_rows={}; archive_log=[]
    specs=[(None,i) for i in range(1,101)] if ticker=="AAPL" else [(y,i) for y in (2023,2024,2025) for i in range(1,101)]
    finished_years=set()
    for year,page in specs:
        if year in finished_years: continue
        url=p["source_policy"]["sources"][ticker].format(year=year,page=page)
        try: html,meta=fetch(url)
        except ValueError as e:
            archive_log.append({"url":url,"status":"failed","reason":str(e)})
            finished_years.add(year);continue
        rows=archive_rows(ticker,url,html)
        new=0
        for row in rows:
            if "2023-01-01"<=row["date"]<="2025-12-31":
                if row["url"] not in all_rows: new+=1
                all_rows[row["url"]]=row
        archive_log.append({"url":url,"status":"ok","rows":len(rows),"new_in_range":new})
        if not rows or (page>1 and new==0 and ticker!="AAPL"): finished_years.add(year)
        if ticker=="AAPL" and rows and min(r["date"] for r in rows)<"2023-01-01": break
    result={"ticker":ticker,"candidates":sorted(all_rows.values(),key=lambda r:(r["date"],r["url"])),"archives":archive_log}
    save(ROOT/"data"/"discovery"/(ticker+".json"),result)
    print("DISCOVER",ticker,len(all_rows),"dated articles",flush=True)
    return result

def legacy_exclusions():
    urls=set();dates=set();case_ids=set()
    for path in (REPO/"jev_model_eval"/"qualitative_news_tests_2026-10-17").glob("*.json"):
        item=read(path); case=item.get("case",item.get("CASE",{}))
        if not case:
            request=item.get("stages",{}).get("event",{}).get("request",{})
            case=request.get("state",{})
        case_ids.add(case.get("case_id",path.stem))
        for article in case.get("articles",[]):
            if article.get("url"): urls.add(canonical_url(article["url"]))
            date=(article.get("published_at") or article.get("publication_date") or case.get("decision_time") or "")[:10]
            if re.fullmatch(r"\d{4}-\d\d-\d\d",date): dates.add(date)
        d=(case.get("decision_time") or "")[:10]
        if d: dates.add(d)
    # Also recover source dates from filenames if older record schemas differ.
    for file in (REPO/"jev_model_eval"/"qualitative_news_tests_2026-10-17").glob("*.json"):
        if "previous_attempt" in file.name: continue
        data=read(file)
        def visit(x):
            if isinstance(x,dict):
                for k,v in x.items():
                    if k in ("decision_time","published_at") and isinstance(v,str) and re.match(r"\d{4}-\d\d-\d\d",v): dates.add(v[:10])
                    if k=="url" and isinstance(v,str) and v.startswith("http"): urls.add(canonical_url(v))
                    if k not in ("response","raw_response"): visit(v)
            elif isinstance(x,list):
                for v in x: visit(v)
        visit(data)
    return {"urls":sorted(urls),"nvda_dates":sorted(dates),"case_ids":sorted(case_ids)}

def target_window(cutoff):
    t=pd.Timestamp(cutoff)
    first=CAL.date_to_session(t.tz_convert("America/New_York").date(),direction="next")
    if CAL.session_open(first)<=t: first=CAL.next_session(first)
    sessions=CAL.sessions_window(first,5)
    return {"entry_session":sessions[0].date().isoformat(),"exit_session":sessions[-1].date().isoformat(),"sessions":[s.date().isoformat() for s in sessions],"entry_open_at":CAL.session_open(sessions[0]).isoformat(),"exit_close_at":CAL.session_close(sessions[-1]).isoformat()}

def article_text(row,control=False):
    html,meta=fetch(row["url"]); soup=BeautifulSoup(html,"html.parser")
    title=soup.find("h1"); title=title.get_text(" ",strip=True) if title else row["title"]
    selectors={"AAPL":[".pagebody-copy"],"AMD":[".xn-content",".press-release-content",".news-details"],"NVDA":[".release-body",".content-body",".article-body",".article-content"],"META":[".entry-content"],"MSFT":[".entry-content"],"NASA":[".entry-content","article"]}
    nodes=[];selector=None
    for sel in selectors[row["ticker"]]+["article","main"]:
        nodes=soup.select(sel)
        if nodes and len(" ".join(n.get_text(" ",strip=True) for n in nodes))>=(150 if control else 350): selector=sel;break
    if not nodes or selector is None: raise ValueError("No substantive article-body selector")
    for node in nodes:
        for remove in node.select("script,style,nav,header,footer,aside,form,.sharedaddy,.related-posts,.social-share,.media-contacts,.contacts"):
            remove.decompose()
    paragraphs=[]
    for node in nodes:
        elements=node.find_all(["p","h2","h3","li","table"],recursive=True)
        if not elements: paragraphs.append(node.get_text(" ",strip=True))
        else:
            paragraphs += [e.get_text(" ",strip=True) for e in elements if not e.find_parent(["li","table"])]
    paragraphs=[re.sub(r"\s+"," ",t).strip() for t in paragraphs if len(t.strip())>12]
    text="\n\n".join(dict.fromkeys(paragraphs))
    if len(text)<(150 if control else 350): raise ValueError("Extracted body too short")
    truncated=len(text)>10000
    if truncated:
        text=text[:10000]; boundary=text.rfind("\n\n")
        if boundary>6000: text=text[:boundary]
    published=None;modified=None
    for name in ("article:published_time","datePublished","pubdate","date"):
        tag=soup.find("meta",attrs={"property":name}) or soup.find("meta",attrs={"name":name})
        if tag and tag.get("content"): published=tag["content"];break
    tag=soup.find("meta",attrs={"property":"article:modified_time"})
    if tag: modified=tag.get("content")
    return {"title":title,"url":row["url"],"source_company":row["ticker"],"publication_date":row["date"],"displayed_publication_time":published,"publication_date_source":"dated publisher archive" if not control else "date in NASA APOD source URL/title","first_observed_at":meta["observed_at"],"retrieved_at":meta["observed_at"],"modified_time":modified,"historical_version_uncertain":True,"historical_version_note":"Retrieved now; old displayed date does not establish that this exact text existed at the cutoff.","text_kind":"publisher_body_excerpt" if truncated else "publisher_body_extracted","text":text,"extraction_selector":selector,"text_sha256":hashlib.sha256(text.encode()).hexdigest(),"raw_source_sha256":meta["sha256"],"raw_source_file":"data/raw_sources/"+digest(row["url"])+".html"}

def case_from_article(ticker,split,article,group,control=False):
    cutoff=datetime.fromisoformat(article["publication_date"]+"T23:59:59").replace(tzinfo=ZoneInfo("America/New_York")).isoformat()
    case={"case_id":ticker+"-"+article["publication_date"]+"-"+article["text_sha256"][:10],"group_id":group,"split":split,"company":{"ticker":ticker,**CONTEXT[ticker]},"articles":[article],"focal_event":article["title"],"decision_time":cutoff,"control":control,"company_baselines":[],"assumptions":["Retrospective reconstruction; exact historical article version is unverified.","Forecast cutoff is the end of the publisher's displayed date in America/New_York."],"expectations":{"status":"not_provided","details":"No point-in-time analyst consensus or market-implied expectation is available."},"market_context":{"status":"not_provided","details":"Legacy baseline receives no market observations, matching the earlier experiment."},"magnitude_inputs":None,"forecast_target":{"entry_rule":"First regular-session open strictly after decision_time.","exit_rule":"Fifth regular-session close, counting entry session as one.","return_type":"raw","neutral_band":0.01},"window":target_window(cutoff)}
    return case

def collect():
    if (ROOT/"frozen"/"dataset.json").exists(): raise ValueError("Dataset is already frozen; collection cannot change it")
    if not (ROOT/"frozen"/"protocol.json").exists():
        save(ROOT/"frozen"/"existing_files.json",protection_manifest())
        save(ROOT/"frozen"/"protocol.json",protocol())
        save(ROOT/"frozen"/"protocol_stamp.json",{"frozen_at":now(),"sha256":digest(protocol()),"new_returns_acquired":False})
    elif digest(protocol())!=digest(read(ROOT/"frozen"/"protocol.json")): raise ValueError("Protocol differs from frozen version")
    exclusions=legacy_exclusions();save(ROOT/"frozen"/"legacy_exclusions.json",exclusions)
    with ThreadPoolExecutor(max_workers=3) as pool: results=list(pool.map(discover_company,protocol()["universe"]))
    cases=[];rejections=[];seen_text=set();p=protocol()
    for result in results:
        ticker=result["ticker"];groups=[];block=[];start=None
        for row in result["candidates"]:
            d=datetime.fromisoformat(row["date"])
            old=row["url"] in exclusions["urls"] or (ticker=="NVDA" and any(abs((d-datetime.fromisoformat(x)).days)<=7 for x in exclusions["nvda_dates"]))
            if old: rejections.append({**row,"reason":"previously inspected source or nearby legacy NVIDIA event"});continue
            if start is None or (d-start).days>7:
                if block: groups.append(block)
                block=[];start=d
            block.append(row)
        if block: groups.append(block)
        anchors=[]
        for block in groups:
            row=min(block,key=lambda r:(title_category(r),digest({"seed":p["seed"],"url":r["url"]})))
            anchors.append({**row,"group_id":ticker+"-week-"+block[0]["date"]})
        anchors.sort(key=lambda r:(r["date"],r["url"]))
        for split,spec in p["splits"].items():
            candidates=[r for r in anchors if spec["start"]<=r["date"]<=spec["end"]]
            quota=spec["issuer_quota_per_company"];used=set();accepted=0
            for j in range(quota):
                center=(j+0.5)*len(candidates)/quota-0.5
                if j==0 and any(title_category(r)<=1 for r in candidates):
                    order=sorted(range(len(candidates)),key=lambda i:(title_category(candidates[i]) if title_category(candidates[i])<=1 else 9,digest({"seed":p["seed"],"url":candidates[i]["url"]})))
                elif j==1 and any(title_category(r)==2 for r in candidates):
                    order=sorted(range(len(candidates)),key=lambda i:(title_category(candidates[i])!=2,digest({"seed":p["seed"],"url":candidates[i]["url"]})))
                else: order=sorted(range(len(candidates)),key=lambda i:(abs(i-center),i))
                for i in order:
                    if i in used:continue
                    used.add(i);row=candidates[i]
                    try:
                        article=article_text(row)
                        if article["text_sha256"] in seen_text: raise ValueError("Duplicate extracted text")
                        case=case_from_article(ticker,split,article,row["group_id"])
                        next_start={"train":"2024-07-01","validation":"2025-07-01"}.get(split)
                        if next_start and case["window"]["exit_session"]>=next_start: raise ValueError("Purged label window crossing next split")
                        seen_text.add(article["text_sha256"]);cases.append(case);accepted+=1
                        print("CASE",split,ticker,article["publication_date"],article["text_kind"],len(article["text"]),flush=True)
                        break
                    except ValueError as e: rejections.append({**row,"split":split,"reason":str(e)})
            if accepted<quota: print("SHORTFALL",ticker,split,accepted,"of",quota,flush=True)
    for split in p["splits"]:
        for ticker,date in zip(p["universe"],p["controls"][split+"_dates"]):
            row={"ticker":"NASA","date":date,"title":"NASA Astronomy Picture of the Day "+date,"url":"https://apod.nasa.gov/apod/ap"+datetime.fromisoformat(date).strftime("%y%m%d")+".html"}
            try:
                article=article_text(row,True)
                if article["text_sha256"] in seen_text: raise ValueError("Duplicate control text")
                cases.append(case_from_article(ticker,split,article,"NASA-"+date,True));seen_text.add(article["text_sha256"])
            except ValueError as e: rejections.append({**row,"split":split,"reason":str(e)})
    cases.sort(key=lambda c:(c["decision_time"],c["company"]["ticker"],c["case_id"]))
    save(ROOT/"data"/"cases.json",cases);save(ROOT/"data"/"exclusions.json",rejections)
    save(ROOT/"data"/"coverage.json",{"created_at":now(),"total":len(cases),"intended":150,"by_split":{s:sum(c["split"]==s for c in cases) for s in p["splits"]},"by_company":{t:sum(c["company"]["ticker"]==t for c in cases) for t in p["universe"]},"controls":sum(c["control"] for c in cases),"exclusions":len(rejections),"all_historical_versions_uncertain":True})
    print("COLLECTED",len(cases),"cases; no new returns acquired",flush=True)

def freeze():
    dest=ROOT/"frozen"/"dataset.json"
    if dest.exists(): raise ValueError("Dataset already frozen")
    cases=read(ROOT/"data"/"cases.json")
    if len(cases)<30: raise ValueError("Fewer than 30 real cases; investigate source coverage before freezing")
    # A selector-based extraction is not certified full text, even below the cap.
    # Clarify provenance before freezing; do not alter any source text or membership.
    for case in cases:
        for article in case["articles"]:
            article["original_extraction_kind"]=article["text_kind"]
            article["text_kind"]="publisher_excerpt"
            article["completeness"]="Extracted body passages; completeness is not independently certified. No AI summary."
            if case["control"]:
                expected=datetime.fromisoformat(article["publication_date"])
                raw=BeautifulSoup((ROOT/article["raw_source_file"]).read_text(encoding="utf-8"),"html.parser")
                actual_title=raw.find("h1") or raw.find("title")
                if actual_title: article["title"]=actual_title.get_text(" ",strip=True)
                normalized=re.sub(r"[^a-z0-9]","",(article["title"]+" "+(raw.title.get_text(" ",strip=True) if raw.title else "")).lower())
                dateline=(str(expected.year)+expected.strftime("%B").lower()+str(expected.day))
                if dateline not in normalized: raise ValueError("NASA historical dateline does not match intended date: "+case["case_id"])
    save(ROOT/"data"/"cases.json",cases)
    assert len({c["case_id"] for c in cases})==len(cases)
    assert len({c["group_id"] for c in cases})==len(cases)
    assert len({a["text_sha256"] for c in cases for a in c["articles"]})==len(cases)
    for split in ("train","validation"):
        boundary={"train":"2024-07-01","validation":"2025-07-01"}[split]
        assert all(c["window"]["exit_session"]<boundary for c in cases if c["split"]==split)
    save(dest,{"frozen_at":now(),"cases_sha256":digest(cases),"protocol_sha256":digest(protocol()),"case_ids":[c["case_id"] for c in cases],"groups":{c["case_id"]:c["group_id"] for c in cases},"splits":{s:[c["case_id"] for c in cases if c["split"]==s] for s in protocol()["splits"]},"evaluator_sha256":hashlib.sha256((ROOT/"evaluate.py").read_bytes()).hexdigest(),"label_code_sha256":hashlib.sha256((ROOT/"data.py").read_bytes()).hexdigest()})
    print("FROZEN",len(cases),"cases; final-test labels remain uncreated",flush=True)

def verify_frozen():
    f=read(ROOT/"frozen"/"dataset.json")
    if f["cases_sha256"]!=digest(read(ROOT/"data"/"cases.json")): raise ValueError("Dataset changed after freeze")
    if f["protocol_sha256"]!=digest(protocol()): raise ValueError("Protocol changed after freeze")
    if f["evaluator_sha256"]!=hashlib.sha256((ROOT/"evaluate.py").read_bytes()).hexdigest(): raise ValueError("Evaluator changed after freeze")
    if f["label_code_sha256"]!=hashlib.sha256((ROOT/"data.py").read_bytes()).hexdigest(): raise ValueError("Label/calendar/data code changed after freeze")
    return f

def download_prices(ticker,end,phase):
    import yfinance as yf
    yf.set_tz_cache_location(str(ROOT/"data"/"yfinance_cache"))
    dest=ROOT/"data"/"prices"/phase/(ticker+".json")
    if dest.exists(): return read(dest)["bars"]
    frame=yf.Ticker(ticker).history(start="2022-10-01",end=end,interval="1d",auto_adjust=False,actions=True,repair=False,raise_errors=True)
    if frame.empty: raise ValueError("Empty price download: "+ticker)
    bars=[]
    for index,row in frame.iterrows():
        bars.append({"date":str(index.date()),"open":float(row["Open"]) if pd.notna(row["Open"]) else None,"close":float(row["Close"]) if pd.notna(row["Close"]) else None,"volume":int(row["Volume"]) if pd.notna(row["Volume"]) else None,"dividends":float(row.get("Dividends",0)),"split":float(row.get("Stock Splits",0))})
    save(dest,{"ticker":ticker,"retrieved_at":now(),"source":"Yahoo Finance through yfinance 0.2.66","start":"2022-10-01","end_exclusive":end,"auto_adjust":False,"actions":True,"repair":False,"bars":bars})
    return bars

def label_case(case,bars):
    lookup={r["date"]:r for r in bars}; w=case["window"]
    status="ok";ret=None;label=None
    entry=lookup.get(w["entry_session"]);exit=lookup.get(w["exit_session"])
    if any(lookup.get(s,{}).get("split",0) for s in w["sessions"]):status="split_in_target_window"
    elif entry is None or exit is None:status="missing_target_bar"
    elif any(v is None or not math.isfinite(v) or v<=0 for v in (entry["open"],exit["close"])):status="invalid_target_price"
    else:
        exact=Decimal(str(exit["close"]))/Decimal(str(entry["open"]))-1
        ret=float(exact);label="up" if exact>Decimal("0.01") else "down" if exact<Decimal("-0.01") else "flat"
    return {"case_id":case["case_id"],"status":status,"return":ret,"label":label,**w,"entry_open":entry["open"] if entry else None,"exit_close":exit["close"] if exit else None}

def market_features(case,stock,spy):
    cutoff=pd.Timestamp(case["decision_time"])
    usable=[s.date().isoformat() for s in CAL.sessions if CAL.session_close(s)<=cutoff]
    needed=usable[-21:]
    result=[]
    for bars in (stock,spy):
        bydate={r["date"]:r for r in bars}
        prices=[bydate.get(s,{}).get("close") for s in needed]
        if len(prices)<21 or any(x is None or not math.isfinite(x) or x<=0 for x in prices):
            return [None]*10
        values=np.array(prices)
        result += [float(values[-1]/values[-1-h]-1) for h in (1,5,20)]
        result += [float(np.std(values[1:]/values[:-1]-1,ddof=1))]
    result += [result[1]-result[5],result[2]-result[6]]
    return result

def prepare_prices(phase):
    verify_frozen()
    if phase=="final" and not (ROOT/"frozen"/"selection.json").exists(): raise ValueError("Final prices require frozen selection")
    if phase=="development" and (ROOT/"frozen"/"selection.json").exists(): raise ValueError("Development closed after selection")
    end="2025-07-01" if phase=="development" else "2026-01-15"
    prices={}
    for t in protocol()["universe"]+["SPY"]:
        try: prices[t]=download_prices(t,end,phase);print("PRICES",phase,t,len(prices[t]),flush=True)
        except Exception as e:
            save(ROOT/"records"/("price_failure_"+phase+"_"+t+".json"),{"at":now(),"ticker":t,"error_type":type(e).__name__,"message":str(e)[:250]})
            prices[t]=[];print("PRICE FAILURE",t,type(e).__name__,flush=True)
    cases=read(ROOT/"data"/"cases.json")
    cases=[c for c in cases if (c["split"]=="test")== (phase=="final")]
    outcomes={};features={}
    for c in cases:
        t=c["company"]["ticker"];outcomes[c["case_id"]]=label_case(c,prices[t]);features[c["case_id"]]=market_features(c,prices[t],prices["SPY"])
    save(ROOT/"data"/("test_outcomes.json" if phase=="final" else "development_outcomes.json"),outcomes)
    save(ROOT/"data"/("test_market_features.json" if phase=="final" else "development_market_features.json"),features)
    return outcomes,features
