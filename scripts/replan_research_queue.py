#!/usr/bin/env python3
import json,sys,pathlib,re
from datetime import datetime,timezone

MAX_REPLAN_DEPTH=1

def depth(task_id):
    return len(re.findall(r"-replan-1", str(task_id)))

def rotated_queries(b):
    return [
      f'"{b}" "Букова" "опыт"',
      f'"{b}" "Букова" "отзыв"',
      f'"{b}" "Букова" "история"',
      f'"{b}" "Букова" "наблюдение"',
      f'"{b}" "Букова" "эксперимент"',
      f'"{b}" "Букова" "до" "после"',
      f'"{b}" "Буковник" "упражнение"',
      f'"{b}" "Буковы" "применение"'
    ]

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
            if v.get("status")!="PASS":
                reason="verification_incomplete"
            elif n.get("status")!="PASS" or not any(c.get("status")=="READY_FOR_REVIEW" for c in n.get("candidates",[])):
                reason="normalization_incomplete"
        if not reason: continue
        if depth(rid)>=MAX_REPLAN_DEPTH:
            t["status"]="EXHAUSTED"; t["exhausted_at"]=now; t["exhausted_reason"]=reason
            continue
        nid=rid+"-replan-1"
        if nid not in existing:
            b=t.get("bukova","")
            additions.append({
              "task_id":nid,"canonical_entry_id":t.get("canonical_entry_id"),"bukova":b,
              "status":"PENDING","priority":"replan","track":"BUKOVY_FIRST",
              "created_at":now,"attempt":0,"max_attempts":1,
              "queries":rotated_queries(b),"reason":reason,"parent_task_id":rid
            })
            existing.add(nid)
    q["tasks"].extend(additions); q["updated_at"]=now
    q["replanned_count"]=q.get("replanned_count",0)+len(additions)
    q["queue_health"]={"policy":"single-rotated-replan","max_replan_depth":MAX_REPLAN_DEPTH,
                       "updated_at":now,"new_replans":len(additions)}
    json.dump(q,open(queue_path,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
if __name__=="__main__": raise SystemExit(main())
