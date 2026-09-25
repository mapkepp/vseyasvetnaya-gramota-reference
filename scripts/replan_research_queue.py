#!/usr/bin/env python3
import json,sys,pathlib
from datetime import datetime,timezone

def main():
    queue_path=pathlib.Path(sys.argv[1]); results_dir=pathlib.Path(sys.argv[2])
    manifest_path=pathlib.Path(sys.argv[3]) if len(sys.argv)>3 else results_dir/"cycle-task-manifest.json"
    q=json.load(open(queue_path,encoding="utf-8"))
    manifest=json.load(open(manifest_path,encoding="utf-8")) if manifest_path.exists() else {"task_ids":[]}
    allowed=set(manifest.get("task_ids",[])); existing={t.get("task_id") for t in q.get("tasks",[])}
    additions=[]; now=datetime.now(timezone.utc).isoformat()
    for t in q.get("tasks",[]):
        rid=t.get("task_id")
        if rid not in allowed or t.get("status") not in ("DONE","FAILED"): continue
        reason=None
        if t.get("status")=="FAILED":
            reason="worker_failed"
        else:
            vf=results_dir/(rid+".verified.json")
            nf=results_dir/(rid+".normalized.json")
            try: v=json.load(open(vf,encoding="utf-8"))
            except Exception: v={"status":"INCOMPLETE"}
            try: n=json.load(open(nf,encoding="utf-8"))
            except Exception: n={"status":"INCOMPLETE","candidate_count":0}
            if not v.get("verification") or v.get("status")!="PASS":
                reason="verification_incomplete"
            elif n.get("status")!="PASS" or not any(c.get("status")=="READY_FOR_REVIEW" for c in n.get("candidates",[])):
                reason="normalization_incomplete"
        if reason:
            nid=rid+"-replan-1"
            if nid not in existing:
                b=t.get("bukova","")
                additions.append({
                  "task_id":nid,"bukova":b,"status":"PENDING","priority":"replan","created_at":now,
                  "queries":[f'"{b}" практика Букова форум',f'"{b}" "нанес" Букова',f'"{b}" "получил результат"',f'"{b}" "применял" практика',f'"{b}" "получила результат" Буков'],
                  "reason":reason,"parent_task_id":rid
                })
                existing.add(nid)
    q["tasks"].extend(additions); q["updated_at"]=now
    q["replanned_count"]=q.get("replanned_count",0)+len(additions)
    json.dump(q,open(queue_path,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
if __name__=="__main__": raise SystemExit(main())
