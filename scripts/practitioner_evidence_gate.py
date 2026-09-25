#!/usr/bin/env python3
import json,sys,pathlib
from datetime import datetime,timezone

def main():
    root=pathlib.Path(sys.argv[1]); ready=[]; incomplete=[]
    for f in root.glob("*.normalized.json"):
        d=json.load(open(f,encoding="utf-8"))
        for c in d.get("candidates",[]):
            (ready if c.get("status")=="READY_FOR_REVIEW" else incomplete).append(c)
    payload={
      "schema_version":"1.0","updated_at":datetime.now(timezone.utc).isoformat(),
      "evidence":"MEASURED","status":"PASS" if ready else "INCOMPLETE",
      "ready_for_human_review":len(ready),"incomplete":len(incomplete),
      "canonical_mutation":"DISABLED",
      "candidates":[
        {"candidate_id":c["candidate_id"],"practitioner":c["practitioner"],"bukova":c["bukova"],
         "action":c["action"],"reported_result":c["reported_result"],"source_url":c["source_url"]}
        for c in ready
      ],
      "gate_rules":[
        "identifiable practitioner required",
        "specific canonical Bukova required",
        "concrete action required",
        "separately reported result/observation required",
        "source URL required",
        "candidate remains anecdotal and source-attributed"
      ]
    }
    json.dump(payload,open(root/"practitioner-evidence-gate.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
if __name__=="__main__": raise SystemExit(main())
