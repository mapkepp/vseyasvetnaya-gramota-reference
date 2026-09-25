#!/usr/bin/env python3
import json,sys,pathlib
from datetime import datetime,timezone

def main():
    root=pathlib.Path(sys.argv[1]); dest=root.parent/"practitioner-review-queue.json"
    old={}
    if dest.exists():
        prior=json.load(open(dest,encoding="utf-8"))
        old={x.get("candidate_id"):x for x in prior.get("items",[])}
    candidates={}
    gate=root/"practitioner-evidence-gate.json"
    if gate.exists():
        data=json.load(open(gate,encoding="utf-8"))
        for c in data.get("candidates",[]):
            cid=c["candidate_id"]
            item={"candidate_id":cid,"status":old.get(cid,{}).get("status","PENDING_HUMAN_REVIEW"),
                  "practitioner":c["practitioner"],"bukova":c["bukova"],"action":c["action"],
                  "reported_result":c["reported_result"],"source_url":c["source_url"],
                  "evidence":"MEASURED","canonical_mutation":"DISABLED"}
            candidates[cid]=item
    payload={"schema_version":"1.0","updated_at":datetime.now(timezone.utc).isoformat(),
             "status":"READY" if candidates else "EMPTY","evidence":"MEASURED",
             "queue_count":sum(1 for x in candidates.values() if x["status"]=="PENDING_HUMAN_REVIEW"),
             "review_policy":"Human review required before any canonical practitioner-history mutation.",
             "items":list(candidates.values())}
    json.dump(payload,open(dest,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
if __name__=="__main__": main()
