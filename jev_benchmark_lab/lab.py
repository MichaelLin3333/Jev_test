"""Command line entry point. Implementation stays inside this folder."""
from pathlib import Path
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent

def probe():
    import requests
    urls = [
        "https://ir.amd.com/news-events/press-releases?year=2024",
        "https://nvidianews.nvidia.com/news?page=10",
        "https://www.apple.com/newsroom/archive/?page=30",
        "https://about.fb.com/news/2024/",
        "https://blogs.microsoft.com/blog/2024/",
        "https://apod.nasa.gov/apod/ap250715.html",
    ]
    headers = {"User-Agent": "JevBenchmarkLab/0.1 (+https://github.com/MichaelLin3333/Jev_test)"}
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=25)
            raw=ROOT/"data"/"source_probe"
            raw.mkdir(parents=True,exist_ok=True)
            (raw/(hashlib.sha256(url.encode()).hexdigest()+".html")).write_text(r.text,encoding="utf-8")
            print(json.dumps({"url": url,"status":r.status_code,"bytes":len(r.content),"sample":r.text[:100] if r.status_code != 200 else None}),flush=True)
            if r.status_code==200:
                from bs4 import BeautifulSoup
                soup=BeautifulSoup(r.text,"html.parser")
                links=[{"href":a.get("href"),"title":a.get_text(" ",strip=True)[:110]} for a in soup.find_all("a",href=True) if any(z in a.get("href","") for z in ["/news/","/newsroom/202","/blog/202","press-release"]) and len(a.get_text(" ",strip=True))>20]
                print(json.dumps({"article_links":links[:8],"time_tags":[str(t)[:200] for t in soup.find_all("time")[:2]],"next":[str(a)[:250] for a in soup.select("a.next,a[rel=next],.pagination a")[:5]]}),flush=True)
            if r.status_code == 200 and "sec.gov/submissions" in url:
                data = r.json()
                print(json.dumps({"company":data.get("name"),"forms":len(data["filings"]["recent"]["form"]),"history_files":data["filings"]["files"]}),flush=True)
        except Exception as e:
            print(json.dumps({"url":url,"error_type":type(e).__name__}),flush=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command")
    parser.add_argument("args",nargs="*")
    args=parser.parse_args()
    if args.command=="probe": return probe()
    if args.command=="smoke":
        from .experiment import smoke
        return smoke()
    if args.command=="collect":
        from .data import collect
        return collect()
    if args.command=="freeze":
        from .data import freeze
        return freeze()
    if args.command in ("develop","final"):
        from . import experiment
        return getattr(experiment,args.command)()
    if args.command=="report":
        from .report import write_report
        return write_report()
    if args.command=="audit":
        from .common import audit_protection
        print(json.dumps(audit_protection()));return
    if args.command=="test":
        import unittest
        suite=unittest.defaultTestLoader.loadTestsFromName("jev_benchmark_lab.test_lab")
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        if not result.wasSuccessful():raise SystemExit(1)
        return
    if args.command=="status":
        for file in ("data/coverage.json","frozen/selection.json","records/final_results.json"):
            p=ROOT/file
            if p.exists(): print(file,p.read_text(encoding="utf-8")[:500])
        return
    raise SystemExit("Command implementation is being prepared: "+args.command)

if __name__=="__main__": main()
