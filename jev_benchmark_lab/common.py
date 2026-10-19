"""Small JSON, hashing and immutable request-cache helpers."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import threading
import time
import requests

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parent
LOCK=threading.Lock()
LAST={}

def now(): return datetime.now(timezone.utc).isoformat()
def canonical(value): return json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(",",":"))
def digest(value): return hashlib.sha256((value if isinstance(value,bytes) else canonical(value).encode("utf-8"))).hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def save(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    temporary.replace(path)
def append(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with LOCK:
        with path.open("a",encoding="utf-8") as f: f.write(canonical(value)+"\n")
def protocol(): return read(ROOT/"protocol.json")

def fetch(url):
    """Cache public HTML/JSON with actual observation time; never backdate it."""
    from urllib.parse import urlparse
    key=digest(url); folder=ROOT/"data"/"raw_sources"; meta=folder/(key+".json"); body=folder/(key+".html")
    if meta.exists():
        item=read(meta)
        if item["status"]!=200: raise ValueError("Cached source failure HTTP "+str(item["status"]))
        return body.read_text(encoding="utf-8"),item
    headers={"User-Agent":"JevBenchmarkLab/0.1 (+https://github.com/MichaelLin3333/Jev_test)"}
    for attempt in range(3):
        host=urlparse(url).hostname
        with LOCK:
            delay=max(0,0.25-(time.monotonic()-LAST.get(host,-100)))
            if delay: time.sleep(delay)
            LAST[host]=time.monotonic()
        try:
            r=requests.get(url,headers=headers,timeout=35)
            item={"url":url,"resolved_url":r.url,"observed_at":now(),"status":r.status_code,"bytes":len(r.content),"sha256":hashlib.sha256(r.content).hexdigest(),"attempt":attempt+1,"content_type":r.headers.get("Content-Type"),"last_modified":r.headers.get("Last-Modified")}
            append(folder/"attempts.jsonl",item)
            if r.status_code==200:
                if len(r.content)>6000000: raise ValueError("Source exceeds 6 MB limit")
                r.encoding=r.encoding if r.encoding and r.encoding.lower()!="iso-8859-1" else "utf-8"
                text=r.text
                folder.mkdir(parents=True,exist_ok=True);body.write_text(text,encoding="utf-8");save(meta,item)
                return text,item
            if r.status_code not in (429,500,502,503,504) or attempt==2:
                save(meta,item); raise ValueError("Source HTTP "+str(r.status_code))
            time.sleep(min(60,max([2,5,10][attempt],float(r.headers.get("Retry-After","0")) if r.headers.get("Retry-After","0").isdigit() else 0)))
        except requests.RequestException as e:
            append(folder/"attempts.jsonl",{"url":url,"observed_at":now(),"attempt":attempt+1,"error_type":type(e).__name__})
            if attempt==2: raise ValueError("Source transport failed: "+type(e).__name__) from None
            time.sleep([2,5][attempt])

def protection_manifest():
    files=[]
    for name in ["jev_model_eval","jev_news"]:
        files += [p for p in (REPO/name).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    files += [p for p in REPO.iterdir() if p.is_file() and p.suffix in (".md",".toml")]
    return {str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}

def audit_protection():
    expected=read(ROOT/"frozen"/"existing_files.json")
    actual=protection_manifest()
    changed=[p for p,h in expected.items() if actual.get(p)!=h]
    result={"checked_at":now(),"checked_files":len(expected),"changed_or_missing":changed,"passed":not changed}
    save(ROOT/"records"/"preservation_audit.json",result)
    if changed: raise ValueError("Existing project files changed: "+str(changed))
    return result
