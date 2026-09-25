#!/usr/bin/env python3
import json,sys,urllib.parse,urllib.request,html
from html.parser import HTMLParser
from datetime import datetime,timezone
class P(HTMLParser):
 def __init__(self): super().__init__(); self.a=False; self.u=""; self.b=[]; self.r=[]
 def handle_starttag(self,t,a):
  a=dict(a)
  if t=="a" and "result__a" in a.get("class",""): self.a=True; self.u=a.get("href",""); self.b=[]
 def handle_data(self,d):
  if self.a:self.b.append(d)
 def handle_endtag(self,t):
  if t=="a" and self.a:
   z=" ".join("".join(self.b).split())
   if self.u and z:self.r.append((z,html.unescape(self.u)))
   self.a=False
def main():
 task=json.load(open(sys.argv[1],encoding="utf-8")); out=sys.argv[2]; found={}
 for q in task.get("queries",[]):
  try:
   u="https://html.duckduckgo.com/html/?"+urllib.parse.urlencode({"q":q,"kl":"ru-ru"})
   req=urllib.request.Request(u,headers={"User-Agent":"ToolboxResearchBot/1.0"})
   body=urllib.request.urlopen(req,timeout=25).read().decode("utf-8","replace")
   p=P(); p.feed(body)
   for title,url in p.r[:8]: found.setdefault(url,{"title":title,"queries":[]})["queries"].append(q)
  except Exception: pass
 findings=[{"claim":"Discovered public-web source; requires verification before use.","sources":[{"url":u,"title":m["title"]}],"evidence_type":"web_discovery","confidence":"UNSPECIFIED","conflicts":[],"discovery_queries":m["queries"]} for u,m in list(found.items())[:8]]
 json.dump({"schema_version":"1.0","task_id":task["task_id"],"bukova":task.get("bukova"),"status":"PASS" if findings else "FAIL","evidence":"MEASURED","generated_at":datetime.now(timezone.utc).isoformat(),"queries":task.get("queries",[]),"search_engine":"github-actions-public-web","findings":findings},open(out,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
 return 0 if findings else 1
if __name__=="__main__": raise SystemExit(main())
