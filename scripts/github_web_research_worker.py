#!/usr/bin/env python3
import json,sys,urllib.parse,urllib.request,html,re,os
from html.parser import HTMLParser
from datetime import datetime,timezone

SEARCH_PROVIDERS=[
 ("bing","https://www.bing.com/search?q={q}&count=10"),
 ("duckduckgo","https://html.duckduckgo.com/html/?q={q}&kl=ru-ru"),
 ("google","https://www.google.com/search?q={q}&num=10"),
 ("yahoo","https://search.yahoo.com/search?p={q}")
]

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.current=None
    def handle_starttag(self,t,a):
        if t!="a": return
        d=dict(a); h=d.get("href","")
        if h.startswith("http"):
            self.current=[h,[]]
    def handle_data(self,d):
        if self.current: self.current[1].append(d)
    def handle_endtag(self,t):
        if t=="a" and self.current:
            u=" ".join("".join(self.current[1]).split())
            self.links.append((u,self.current[0])); self.current=None

def fetch(url,headers=None,timeout=20):
    h={"User-Agent":"Mozilla/5.0 (compatible; ToolboxResearchBot/1.1; +https://github.com/mapkepp/vseyasvetnaya-gramota-reference)"}
    if headers: h.update(headers)
    req=urllib.request.Request(url,headers=h)
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return r.read().decode("utf-8","replace")

def clean(u):
    try:
        p=urllib.parse.urlsplit(u)
        if p.scheme not in ("http","https") or not p.netloc: return None
        host=p.netloc.lower()
        blocked=("bing.com","google.com","yahoo.com","duckduckgo.com","search.brave.com")
        if any(host==x or host.endswith("."+x) for x in blocked): return None
        return u
    except Exception: return None

def parse_generic(body):
    p=LinkParser(); p.feed(body); out=[]
    seen=set()
    for title,u in p.links:
        u=clean(u)
        if not u or u in seen or len(title)<4: continue
        seen.add(u); out.append((title[:300],u))
    return out

def github_search(q):
    token=os.environ.get("GITHUB_TOKEN")
    if not token: return []
    url="https://api.github.com/search/code?"+urllib.parse.urlencode({"q":q,"per_page":10})
    body=fetch(url,{"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json"})
    data=json.loads(body)
    return [(x.get("name") or x.get("path",""),x.get("html_url","")) for x in data.get("items",[]) if x.get("html_url")]

def search_query(q, diagnostics):
    encoded=urllib.parse.quote_plus(q)
    for name,template in SEARCH_PROVIDERS:
        try:
            body=fetch(template.format(q=encoded))
            rows=parse_generic(body)
            if rows:
                diagnostics.append({"provider":name,"query":q,"status":"PASS","results":len(rows)})
                return name,rows
            diagnostics.append({"provider":name,"query":q,"status":"EMPTY","results":0})
        except Exception as e:
            diagnostics.append({"provider":name,"query":q,"status":"FAIL","error":type(e).__name__})
    try:
        rows=github_search(q)
        if rows:
            diagnostics.append({"provider":"github-code","query":q,"status":"PASS","results":len(rows)})
            return "github-code",rows
        diagnostics.append({"provider":"github-code","query":q,"status":"EMPTY","results":0})
    except Exception as e:
        diagnostics.append({"provider":"github-code","query":q,"status":"FAIL","error":type(e).__name__})
    return None,[]

def main():
    task=json.load(open(sys.argv[1],encoding="utf-8")); out=sys.argv[2]
    found={}; diagnostics=[]
    queries=list(task.get("queries",[]))
    b=str(task.get("bukova","")).strip()
    if b:
        queries += [
            f'"{b}" "став" Буков',
            f'"{b}" "буквица" практика',
            f'"{b}" "нанос" практика',
            f'"{b}" "результат" практика'
        ]
    for q in queries:
        provider,rows=search_query(q,diagnostics)
        for title,url in rows[:10]:
            found.setdefault(url,{"title":title,"queries":[],"providers":[]})
            found[url]["queries"].append(q)
            if provider and provider not in found[url]["providers"]: found[url]["providers"].append(provider)
        if len(found)>=12: break
    findings=[{
        "claim":"Discovered public-web source; requires human-readable verification before use.",
        "sources":[{"url":u,"title":m["title"]}],
        "evidence_type":"web_discovery","confidence":"UNSPECIFIED","conflicts":[],
        "discovery_queries":m["queries"],"providers":m["providers"]
    } for u,m in list(found.items())[:12]]
    status="PASS" if findings else "FAIL"
    json.dump({
        "schema_version":"1.1","task_id":task["task_id"],"bukova":b,"status":status,
        "evidence":"MEASURED","generated_at":datetime.now(timezone.utc).isoformat(),
        "queries":queries,"search_engine":"github-actions-public-web-multi-provider",
        "findings":findings,"diagnostics":diagnostics,
        "canonical_mutation":"DISABLED"
    },open(out,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
    return 0 if findings else 1
if __name__=="__main__": raise SystemExit(main())
