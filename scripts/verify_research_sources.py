#!/usr/bin/env python3
import json,sys,urllib.request,urllib.parse,re
from html.parser import HTMLParser
from datetime import datetime,timezone

class Text(HTMLParser):
 def __init__(self): super().__init__(); self.parts=[]
 def handle_data(self,d):
  d=" ".join(d.split())
  if d:self.parts.append(d)

def fetch(url):
 req=urllib.request.Request(url,headers={"User-Agent":"ToolboxResearchVerifier/1.0"})
 with urllib.request.urlopen(req,timeout=20) as r:
  return r.read().decode("utf-8","replace")[:200000]

def verify(task,result):
 out=[]
 target=str(task.get("bukova","")).lower()
 for f in result.get("findings",[]):
  for s in f.get("sources",[]):
   url=s.get("url","")
   try:
    raw=fetch(url); p=Text(); p.feed(raw); text=" ".join(p.parts)
    low=text.lower()
    needles=[target]+[str(q).lower() for q in task.get("queries",[])]
    hits=[n for n in needles if n and n in low]
    out.append({"url":url,"title":s.get("title",""),"reachable":True,
                 "bukova_mention":bool(target and target in low),
                 "query_signal_count":len(hits),"matched_signals":hits[:5],
                 "evidence_type":"source_verification","verification":"CANDIDATE" if target in low else "UNCONFIRMED"})
   except Exception as e:
    out.append({"url":url,"title":s.get("title",""),"reachable":False,
                "bukova_mention":False,"query_signal_count":0,"matched_signals":[],
                "evidence_type":"source_verification","verification":"UNREACHABLE",
                "error":type(e).__name__})
 return out

def main():
 task=json.load(open(sys.argv[1],encoding="utf-8"))
 result=json.load(open(sys.argv[2],encoding="utf-8"))
 verified=verify(task,result)
 status="PASS" if any(x["verification"]=="CANDIDATE" for x in verified) else "INCOMPLETE"
 payload={"schema_version":"1.0","task_id":task["task_id"],"bukova":task.get("bukova"),
          "status":status,"evidence":"MEASURED","generated_at":datetime.now(timezone.utc).isoformat(),
          "verification":verified,
          "rule":"Candidate verification only; practitioner claim requires human-readable evidence of practitioner, action, result and source."}
 json.dump(payload,open(sys.argv[3],"w",encoding="utf-8"),ensure_ascii=False,indent=2)
 return 0
if __name__=="__main__": raise SystemExit(main())
