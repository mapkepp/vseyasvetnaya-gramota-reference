#!/usr/bin/env python3
import json,sys,re,urllib.request
from html.parser import HTMLParser
from datetime import datetime,timezone
ACT=re.compile(r"([^.!?\n]{0,250}\b(?:нанесла?|наносил[аи]?|ставил[аи]?|поставил[аи]?|применил[аи]?|применял[аи]?|использовал[аи]?|рисовал[аи]?|носил[аи]?|держал[аи]?|прикладывал[аи]?)\b[^.!?\n]{0,700})",re.I)
RES=re.compile(r"([^.!?\n]{0,300}\b(?:результат|сработал[оаи]?|помогл[оаи]?|ощутил[а]?|почувствовал[а]?|увидел[а]?|получил[а]?|заметил[а]?|эффект)\b[^.!?\n]{0,800})",re.I)
class P(HTMLParser):
 def __init__(self):super().__init__();self.p=[]
 def handle_data(self,d):
  d=" ".join(d.split())
  if d:self.p.append(d)
def main():
 task=json.load(open(sys.argv[1],encoding="utf-8"));ver=json.load(open(sys.argv[2],encoding="utf-8"));out=[];bad={"пользователь","участник","администратор","модератор"}
 for v in ver.get("verification",[]):
  if not v.get("reachable") or v.get("verification")!="CANDIDATE":continue
  try:
   req=urllib.request.Request(v["url"],headers={"User-Agent":"ToolboxEvidenceNormalizer/1.2"});raw=urllib.request.urlopen(req,timeout=25).read().decode("utf-8","replace")[:500000];p=P();p.feed(raw);txt=" ".join(p.p)
  except:continue
  for w in re.split(r"(?<=[.!?])\s+",txt):
   a=ACT.search(w);r=RES.search(w)
   if not a or not r:continue
   practitioner=None
   m=re.search(r"\b(?:пользователь|практик|мастер|автор|участник)\s+([А-ЯЁA-Z][\wЁё-]{1,30})\b",w,re.I)
   if m and m.group(1).casefold() not in bad:practitioner=m.group(1)
   out.append({"candidate_id":task["task_id"]+"::"+str(len(out)+1),"status":"READY_FOR_REVIEW" if practitioner else "CANDIDATE","evidence":"MEASURED","practitioner":practitioner,"bukova":task.get("bukova"),"action":a.group(1).strip(),"reported_result":r.group(1).strip(),"source_url":v["url"],"source_title":v.get("title",""),"source_excerpt_candidates":[w[:2500]],"canonical_mutation":"DISABLED"});break
 payload={"schema_version":"1.1","generated_at":datetime.now(timezone.utc).isoformat(),"task_id":task["task_id"],"canonical_entry_id":task.get("canonical_entry_id"),"bukova":task.get("bukova"),"status":"PASS" if any(x["status"]=="READY_FOR_REVIEW" for x in out) else ("CANDIDATE" if out else "INCOMPLETE"),"evidence":"MEASURED","candidate_count":len(out),"candidates":out}
 json.dump(payload,open(sys.argv[3],"w",encoding="utf-8"),ensure_ascii=False,indent=2)
if __name__=="__main__":main()
