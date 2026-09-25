#!/usr/bin/env python3
import json,sys,urllib.request
from html.parser import HTMLParser
from datetime import datetime,timezone
class Text(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]
    def handle_data(self,d):
        d=" ".join(d.split())
        if d:self.parts.append(d)
def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"ToolboxResearchVerifier/1.1"})
    with urllib.request.urlopen(req,timeout=20) as r:return r.read().decode("utf-8","replace")[:200000]
def main():
    task=json.load(open(sys.argv[1],encoding="utf-8")); result=json.load(open(sys.argv[2],encoding="utf-8")); out=[]
    target=str(task.get("bukova","")).casefold()
    for f in result.get("findings",[]):
      for s in f.get("sources",[]):
        url=s.get("url","")
        try:
          p=Text();p.feed(fetch(url));low=" ".join(p.parts).casefold()
          ok=bool(target and target in low and any(x in low for x in ("буков","буквиц")) and any(x in low for x in ("став","нанес","примен","использовал","практик","результат","эффект")))
          out.append({"url":url,"title":s.get("title",""),"reachable":True,"bukova_mention":target in low,"verification":"CANDIDATE" if ok else "UNCONFIRMED","evidence_type":"source_verification"})
        except Exception as e: out.append({"url":url,"title":s.get("title",""),"reachable":False,"verification":"UNREACHABLE","error":type(e).__name__})
    json.dump({"schema_version":"1.1","task_id":task["task_id"],"canonical_entry_id":task.get("canonical_entry_id"),"bukova":task.get("bukova"),"status":"PASS" if any(x["verification"]=="CANDIDATE" for x in out) else "INCOMPLETE","evidence":"MEASURED","generated_at":datetime.now(timezone.utc).isoformat(),"verification":out},open(sys.argv[3],"w",encoding="utf-8"),ensure_ascii=False,indent=2)
if __name__=="__main__":main()
