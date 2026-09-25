#!/usr/bin/env python3
import json,sys,urllib.request,re
from html.parser import HTMLParser
from datetime import datetime,timezone

class Text(HTMLParser):
 def __init__(self): super().__init__(); self.parts=[]
 def handle_data(self,d):
  d=" ".join(d.split())
  if d:self.parts.append(d)

def fetch(url):
 req=urllib.request.Request(url,headers={"User-Agent":"ToolboxResearchVerifier/1.1"})
 with urllib.request.urlopen(req,timeout=20) as r:
  return r.read().decode("utf-8","replace")[:200000]

DOMAIN_SIGNALS=("буков","буквиц")
PRACTICE_SIGNALS=("став","нанес","примен","использовал","рисовал","носил","прикладывал","практик")
RESULT_SIGNALS=("результат","сработал","помогл","ощутил","почувствовал","увидел","получил","заметил","приснилось","эффект")

def verify(task,result):
 out=[]
 target=str(task.get("bukova","")).casefold()
 for f in result.get("findings",[]):
  for s in f.get("sources",[]):
   url=s.get("url","")
   try:
    raw=fetch(url); p=Text(); p.feed(raw); page_text=" ".join(p.parts); low=page_text.casefold()
    target_present=bool(target and target in low)
    domain_hits=[x for x in DOMAIN_SIGNALS if x in low]
    practice_hits=[x for x in PRACTICE_SIGNALS if x in low]
    result_hits=[x for x in RESULT_SIGNALS if x in low]
    query_hits=[str(q).casefold() for q in task.get("queries",[]) if str(q).casefold() in low]
    eligible=target_present and bool(domain_hits) and bool(practice_hits or result_hits)
    out.append({
      "url":url,"title":s.get("title",""),"reachable":True,
      "bukova_mention":target_present,
      "domain_context":bool(domain_hits),
      "practice_context":bool(practice_hits),
      "result_context":bool(result_hits),
      "query_signal_count":len(query_hits),
      "matched_signals":(domain_hits+practice_hits+result_hits+query_hits)[:8],
      "evidence_type":"source_verification",
      "verification":"CANDIDATE" if eligible else "UNCONFIRMED"
    })
   except Exception as e:
    out.append({"url":url,"title":s.get("title",""),"reachable":False,
                "bukova_mention":False,"domain_context":False,"practice_context":False,"result_context":False,
                "query_signal_count":0,"matched_signals":[],"evidence_type":"source_verification",
                "verification":"UNREACHABLE","error":type(e).__name__})
 return out

def main():
 task=json.load(open(sys.argv[1],encoding="utf-8"))
 result=json.load(open(sys.argv[2],encoding="utf-8"))
 verified=verify(task,result)
 status="PASS" if any(x["verification"]=="CANDIDATE" for x in verified) else "INCOMPLETE"
 payload={"schema_version":"1.1","task_id":task["task_id"],"canonical_entry_id":task.get("canonical_entry_id"),
          "bukova":task.get("bukova"),"status":status,"evidence":"MEASURED",
          "generated_at":datetime.now(timezone.utc).isoformat(),"verification":verified,
          "rule":"Candidate verification requires the Bukova mention plus Bukova-specific context and practice/result context; practitioner claim still requires human-readable evidence."}
 json.dump(payload,open(sys.argv[3],"w",encoding="utf-8"),ensure_ascii=False,indent=2)
 return 0
if __name__=="__main__": raise SystemExit(main())
