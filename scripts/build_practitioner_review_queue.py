#!/usr/bin/env python3
import json,sys,pathlib
from datetime import datetime,timezone
def main():
 root=pathlib.Path(sys.argv[1]);dest=root.parent/"practitioner-review-queue.json";gate=root/"practitioner-evidence-gate.json";data=json.load(open(gate,encoding="utf-8")) if gate.exists() else {};old={}
 if dest.exists():
  try: old={x.get("candidate_id"):x for x in json.load(open(dest,encoding="utf-8")).get("items",[])}
  except: pass
 items=[]
 for c in data.get("candidates",[]):
  items.append({"candidate_id":c["candidate_id"],"status":old.get(c["candidate_id"],{}).get("status","PENDING_HUMAN_REVIEW"),"practitioner":c["practitioner"],"bukova":c["bukova"],"action":c["action"],"reported_result":c["reported_result"],"source_url":c["source_url"],"evidence":"MEASURED","canonical_mutation":"DISABLED"})
 out={"schema_version":"1.0","updated_at":datetime.now(timezone.utc).isoformat(),"status":"READY" if items else "EMPTY","evidence":"MEASURED","queue_count":sum(x["status"]=="PENDING_HUMAN_REVIEW" for x in items),"review_policy":"Human review required before canonical mutation.","items":items}
 json.dump(out,open(dest,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
if __name__=="__main__":main()
