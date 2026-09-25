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

class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.a=None; self.out=[]
    def handle_starttag(self,t,a):
        if t=="a":
            d=dict(a); self.a=[d.get("href",""),[]]
    def handle_data(self,d):
        if self.a:self.a[1].append(d)
    def handle_endtag(self,t):
        if t=="a" and self.a:
            self.out.append((" ".join("".join(self.a[1]).split()),self.a[0])); self.a=None

def fetch(url,headers=None,timeout=20):
    h={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
       "Accept":"text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
       "Accept-Encoding":"identity","Accept-Language":"ru-RU,ru;q=0.9,en;q=0.7"}
    if headers:h.update(headers)
    req=urllib.request.Request(url,headers=h)
    with urllib.request.urlopen(req,timeout=timeout) as r:
        body=r.read().decode("utf-8","replace")
        return r.getcode(),r.geturl(),body

def unwrap(url):
    try:
        p=urllib.parse.urlsplit(url)
        qs=urllib.parse.parse_qs(p.query)
        for key in ("uddg","url","q"):
            if qs.get(key):
                v=qs[key][0]
                if v.startswith("http"): return urllib.parse.unquote(v)
        if p.scheme in ("http","https") and p.netloc:
            return url
    except Exception: pass
    return None

def clean(u):
    u=unwrap(u)
    if not u:return None
    try:
        p=urllib.parse.urlsplit(u)
        host=p.netloc.lower()
        if p.scheme not in ("http","https") or not host:return None
        blocked=("bing.com","google.com","yahoo.com","duckduckgo.com","search.brave.com")
        if any(host==x or host.endswith("."+x) for x in blocked):return None
        return urllib.parse.urlunsplit((p.scheme,p.netloc,p.path,p.query,p.fragment))
    except Exception:return None

def parse_provider(name,body):
    p=AnchorParser(); p.feed(body); rows=[]
    for title,href in p.out:
        keep=False
        if name=="bing":
            keep=bool(re.search(r"<h2",body,re.I) and href)
        elif name=="duckduckgo":
            keep=("result__a" in title or True) and ("uddg=" in href or "http" in href)
        elif name=="google":
            keep=(href.startswith("/url?") or href.startswith("http"))
        elif name=="yahoo":
            keep=("search.yahoo" not in href and href.startswith("http"))
        if not keep: continue
        u=clean(href)
        if not u or len(title)<3: continue
        rows.append((html.unescape(title)[:300],u))
    # generic fallback with provider-independent links
    if not rows:
        for title,href in p.out:
            u=clean(href)
            if u and len(title)>=3: rows.append((html.unescape(title)[:300],u))
    out=[];seen=set()
    for row in rows:
        if row[1] not in seen:seen.add(row[1]);out.append(row)
    return out[:12]

def github_search(q):
    token=os.environ.get("GITHUB_TOKEN")
    if not token:return []
    url="https://api.github.com/search/code?"+urllib.parse.urlencode({"q":q,"per_page":10})
    _,_,body=fetch(url,{"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json"})
    data=json.loads(body)
    return [(x.get("name") or x.get("path",""),x.get("html_url","")) for x in data.get("items",[]) if x.get("html_url")]

def search_query(q,diagnostics):
    encoded=urllib.parse.quote_plus(q)
    for name,template in SEARCH_PROVIDERS:
        try:
            code,final_url,body=fetch(template.format(q=encoded))
            rows=parse_provider(name,body)
            diagnostics.append({"provider":name,"query":q,"status":"PASS" if rows else "EMPTY",
                                "http_status":code,"final_url":final_url,"results":len(rows),
                                "body_chars":len(body)})
            if rows:return name,rows
        except Exception as e:
            diagnostics.append({"provider":name,"query":q,"status":"FAIL","error":type(e).__name__})
    try:
        rows=github_search(q)
        diagnostics.append({"provider":"github-code","query":q,"status":"PASS" if rows else "EMPTY","results":len(rows)})
        if rows:return "github-code",rows
    except Exception as e:
        diagnostics.append({"provider":"github-code","query":q,"status":"FAIL","error":type(e).__name__})
    return None,[]

def main():
    task=json.load(open(sys.argv[1],encoding="utf-8")); out=sys.argv[2]
    b=str(task.get("bukova","")).strip(); found={}; diagnostics=[]
    queries=list(dict.fromkeys(task.get("queries",[])+[
        f'"{b}" "став" Буков',f'"{b}" "буквица" практика',f'"{b}" "нанос" практика',f'"{b}" "результат" практика'
    ]))
    for q in queries:
        provider,rows=search_query(q,diagnostics)
        for title,url in rows:
            found.setdefault(url,{"title":title,"queries":[],"providers":[]})
            found[url]["queries"].append(q)
            if provider and provider not in found[url]["providers"]:found[url]["providers"].append(provider)
        if len(found)>=20:break
    # Conditional external-AI escalation. It is invoked only when discovery
    # coverage is weak and never has authority to write files or canonical data.
    external_ai = {"provider":"none","status":"NOT_NEEDED"}
    if len(found) < 5:
        try:
            import subprocess
            prompt = (
                "For the research task about the Bukova " + b +
                ", propose up to 8 highly specific web-search queries aimed at "
                "first-person practitioner stories, concrete actions, dates, and "
                "observable results. Output one query per line. Never invent evidence."
            )
            p = subprocess.run(
                ["python3","scripts/external_ai_router.py",prompt],
                capture_output=True,text=True,timeout=50,check=False
            )
            if p.stdout.strip():
                external_ai=json.loads(p.stdout)
                extra=external_ai.get("text","")
                ai_queries=[]
                for line in extra.splitlines():
                    line=re.sub(r'^\\s*[-*0-9.)]+\\s*',"",line).strip().strip('"“”')
                    if 8 <= len(line) <= 220 and (" " in line):
                        ai_queries.append(line)
                ai_queries=list(dict.fromkeys(ai_queries))[:8]
                for q2 in ai_queries:
                    provider,rows=search_query(q2,diagnostics)
                    for title,url in rows:
                        found.setdefault(url,{"title":title,"queries":[],"providers":[]})
                        found[url]["queries"].append(q2)
                        if provider and provider not in found[url]["providers"]:
                            found[url]["providers"].append(provider)
                queries=list(dict.fromkeys(queries+ai_queries))[:38]
        except Exception as e:
            external_ai={"provider":"none","status":"ERROR","error":type(e).__name__}

    findings=[{"claim":"Discovered public-web source; requires human-readable verification before use.",
                "sources":[{"url":u,"title":m["title"]}],"evidence_type":"web_discovery",
                "confidence":"UNSPECIFIED","conflicts":[],"discovery_queries":m["queries"],"providers":m["providers"]}
               for u,m in list(found.items())[:12]]
    payload={"schema_version":"1.2","task_id":task["task_id"],"canonical_entry_id":task.get("canonical_entry_id"),"bukova":b,"status":"PASS" if findings else "FAIL",
             "evidence":"MEASURED","generated_at":datetime.now(timezone.utc).isoformat(),
             "queries":queries,"search_engine":"github-actions-public-web-multi-provider",
             "findings":findings,"diagnostics":diagnostics,"external_ai":external_ai,"canonical_mutation":"DISABLED"}
    json.dump(payload,open(out,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
    return 0 if findings else 1
if __name__=="__main__":raise SystemExit(main())
