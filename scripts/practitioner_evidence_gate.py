#!/usr/bin/env python3
import json,sys,pathlib,re
from datetime import datetime,timezone
ACTION=re.compile(r"\b(?:нанесла?|наносил[аи]?|ставил[аи]?|поставил[аи]?|применил[аи]?|применял[аи]?|использовал[аи]?|рисовал[аи]?|носил[аи]?|держал[аи]?|прикладывал[аи]?)\b",re.I)
RESULT=re.compile(r"\b(?:результат|сработал[оаи]?|помогл[оаи]?|ощутил[а]?|почувствовал[а]?|увидел[а]?|получил[а]?|заметил[а]?|эффект)\b",re.I)
def main():
 root=pathlib.Path(sys.argv[1]); ready=[]; rejected=[]
 for f in root.glob("*.normalized.json"):
  d=json.load(open(f,encoding="utf-8"))
  for c in d.get("candidates",[]):
   vals={k:str(c.get(k) or "").strip() for k in ("practitioner","bukova","action","reported_result","source_url")}
   reasons=[k for k,v in vals.items() if not v]
   if vals["practitioner"].casefold() in {"пользователь","участник","администратор","модератор"}:reasons.append("generic_practitioner")
   if not ACTION.search(vals["action"]):reasons.append("no_application_verb")
   if not RESULT.search(vals["reported_result"]):reasons.append("no_result_marker")
   if vals["action"]==vals["reported_result"]:reasons.append("action_equals_result")
   if not any(vals["action"][:90] in str(e) and vals["reported_result"][:90] in str(e) for e in c.get("source_excerpt_candidates",[])):reasons.append("not_same_excerpt")
   (ready if not reasons else rejected).append(c if not reasons else {"candidate_id":c.get("candidate_id"),"reasons":reasons,"source_url":c.get("source_url")})
 out={"schema_version":"1.1","updated_at":datetime.now(timezone.utc).isoformat(),"evidence":"MEASURED","status":"PASS" if ready else "INCOMPLETE","ready_for_human_review":len(ready),"rejected_by_strict_gate":len(rejected),"canonical_mutation":"DISABLED","candidates":[{"candidate_id":c["candidate_id"],"practitioner":c["practitioner"],"bukova":c["bukova"],"action":c["action"],"reported_result":c["reported_result"],"source_url":c["source_url"]} for c in ready],"rejections":rejected}
 json.dump(out,open(root/"practitioner-evidence-gate.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
if __name__=="__main__":main()
