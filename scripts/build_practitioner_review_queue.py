#!/usr/bin/env python3
import json,sys,pathlib
from datetime import datetime,timezone

def main():
    root=pathlib.Path(sys.argv[1])
    candidates=[]
    gate=root/"practitioner-evidence-gate.json"
    if gate.exists():
        data=json.load(open(gate,encoding="utf-8"))
        for c in data.get("candidates",[]):
            candidates.append({
                "candidate_id":c["candidate_id"],
                "status":"PENDING_HUMAN_REVIEW",
                "practitioner":c["practitioner"],
                "bukova":c["bukova"],
                "action":c["action"],
                "reported_result":c["reported_result"],
                "source_url":c["source_url"],
                "evidence":"MEASURED",
                "canonical_mutation":"DISABLED"
            })
    payload={
        "schema_version":"1.0",
        "updated_at":datetime.now(timezone.utc).isoformat(),
        "status":"READY" if candidates else "EMPTY",
        "evidence":"MEASURED",
        "queue_count":len(candidates),
        "review_policy":"Human review required before any canonical practitioner-history mutation.",
        "items":candidates
    }
    dest=root.parent/"practitioner-review-queue.json"
    json.dump(payload,open(dest,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
if __name__=="__main__": main()
