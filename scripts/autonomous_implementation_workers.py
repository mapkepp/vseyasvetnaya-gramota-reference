#!/usr/bin/env python3
import json, pathlib, subprocess, hashlib
from datetime import datetime, timezone

ROOT=pathlib.Path(__file__).resolve().parents[1]
RESEARCH=ROOT/"data/research"
OUT=RESEARCH/"implementation-status.json"
QUEUE=RESEARCH/"implementation-queue.json"
MANIFEST=RESEARCH/"worker-results"/"cycle-task-manifest.json"
REVIEW=RESEARCH/"practitioner-review-queue.json"
ALLOWED_DERIVED=("api/","data/research/","research-status.html")

def run(cmd):
    p=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
    return p.returncode,p.stdout[-4000:],p.stderr[-4000:]

def load(path, default):
    try:return json.loads(path.read_text("utf-8"))
    except Exception:return default

def git_diff():
    _,out,_=run(["git","diff","--name-only"])
    _,cached,_=run(["git","diff","--cached","--name-only"])
    return [x for x in (out+"\n"+cached).splitlines() if x]

def forbidden(paths):
    return [p for p in paths if p and not p.startswith(ALLOWED_DERIVED)]

def agent_api_sync():
    rc,out,err=run(["python3","scripts/build-api.py"])
    if rc!=0:return {"agent":"api-sync","status":"FAIL","evidence":"MEASURED","detail":err or out}
    changed=git_diff()
    bad=forbidden(changed)
    if bad:
        run(["git","restore","--worktree","."])
        return {"agent":"api-sync","status":"FAIL","evidence":"MEASURED","detail":"forbidden modifications: "+", ".join(bad)}
    return {"agent":"api-sync","status":"PASS" if any(p.startswith("api/") for p in changed) else "NO_CHANGES","evidence":"MEASURED","changed":changed}

def agent_research_handoff():
    manifest=load(MANIFEST,{"cycle_id":None,"task_ids":[]})
    review=load(REVIEW,{"queue_count":0,"items":[]})
    results=[]
    for tid in manifest.get("task_ids",[]):
        rp=RESEARCH/"worker-results"/f"{tid}.result.json"
        np=RESEARCH/"worker-results"/f"{tid}.normalized.json"
        r=load(rp,{})
        n=load(np,{})
        results.append({
          "task_id":tid,"canonical_entry_id":r.get("canonical_entry_id",n.get("canonical_entry_id")),
          "bukova":r.get("bukova",n.get("bukova")),"discovery_status":r.get("status","NOT_FOUND"),
          "source_count":len(r.get("findings",[])),"normalized_status":n.get("status","NOT_FOUND"),
          "candidate_count":n.get("candidate_count",0)
        })
    impl=[]
    if review.get("queue_count",0):
        for item in review.get("items",[]):
            impl.append({"implementation_id":"review-"+str(item.get("candidate_id")),"type":"human-approved-data-promotion",
                         "status":"BLOCKED_PENDING_HUMAN_REVIEW","candidate_id":item.get("candidate_id"),
                         "bukova":item.get("bukova"),"safe_rule":"never mutate canonical data automatically"})
    else:
        for x in results:
            if x["discovery_status"]=="PASS" and x["normalized_status"]=="INCOMPLETE":
                impl.append({"implementation_id":"evidence-gap-"+x["task_id"],"type":"research-followup",
                             "status":"PENDING","canonical_entry_id":x["canonical_entry_id"],"bukova":x["bukova"],
                             "safe_rule":"research artifact only; no canonical mutation"})
    queue={"schema_version":"1.0","updated_at":datetime.now(timezone.utc).isoformat(),
           "cycle_id":manifest.get("cycle_id"),"source":"autonomous-research-worker",
           "items":impl,"review_queue_count":review.get("queue_count",0)}
    QUEUE.write_text(json.dumps(queue,ensure_ascii=False,indent=2)+"\n","utf-8")
    return {"agent":"research-handoff","status":"PASS","evidence":"MEASURED",
            "cycle_id":manifest.get("cycle_id"),"implementation_items":len(impl),
            "review_queue_count":review.get("queue_count",0)}

def agent_immutability():
    changed=git_diff()
    bad=forbidden(changed)
    return {"agent":"immutability-audit","status":"FAIL" if bad else "PASS","evidence":"MEASURED",
            "forbidden_changes":bad,"checked_changes":changed}

def main():
    started=datetime.now(timezone.utc)
    a=[agent_api_sync(),agent_research_handoff(),agent_immutability()]
    status="FAIL" if any(x["status"]=="FAIL" for x in a) else "PASS"
    payload={"schema_version":"1.0","updated_at":datetime.now(timezone.utc).isoformat(),
             "started_at":started.isoformat(),"worker":"github-implementation-workers",
             "phase":"IMPLEMENT_VALIDATE_HANDOFF","status":status,"evidence":"MEASURED",
             "agents":a,"canonical_mutation":"DISABLED",
             "promotion":"handled separately after validation",
             "allowed_write_zones":list(ALLOWED_DERIVED)}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n","utf-8")
    print(json.dumps(payload,ensure_ascii=False,indent=2))
    raise SystemExit(1 if status=="FAIL" else 0)
if __name__=="__main__":main()
