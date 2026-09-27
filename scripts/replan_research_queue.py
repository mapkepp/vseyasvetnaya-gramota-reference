#!/usr/bin/env python3
import json,sys,pathlib,re
from datetime import datetime,timezone

MAX_REPLAN_DEPTH=3
MAX_ATTEMPTS_PER_TASK=2

def depth(task_id):
    return len(re.findall(r"-replan-\d+", str(task_id)))

def rotated_queries(b):
    d=depth(b)
    return [
      f'"{b}" "Букова" "опыт" практика',
      f'"{b}" "Букова" "отзыв" результат',
      f'"{b}" "Букова" "история" применение',
      f'"{b}" "Букова" "наблюдение" эффект',
      f'"{b}" "Букова" "эксперимент" результат',
      f'"{b}" "Букова" "до" "после"',
      f'"{b}" "Буковник" упражнение практика',
      f'"{b}" "Буковы" применение опыт',
      f'"{b}" "Букова" мастер практика свидетельство',
      f'"{b}" "Букова" дневник журнал отчёт',
      f'"{b}" "Букова" форум обсуждение комментарии',
      f'"{b}" "Букова" видео лекция семинар разбор'
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
            try: v=json.load(open(results_dir/(rid+".verified.json"),encoding="utf-8"))
            except Exception: v={"status":"INCOMPLETE"}
            try: n=json.load(open(results_dir/(rid+".normalized.json"),encoding="utf-8"))
            except Exception: n={"status":"INCOMPLETE","candidate_count":0}
            if v.get("status")!="PASS": reason="verification_incomplete"
            elif n.get("status")!="PASS" or not any(c.get("status")=="READY_FOR_REVIEW" for c in n.get("candidates",[])):
                reason="normalization_incomplete"
        if not reason: continue
        d=depth(rid)
        if d>=MAX_REPLAN_DEPTH:
            t["status"]="EXHAUSTED"; t["exhausted_at"]=now; t["exhausted_reason"]=reason
            continue
        nid=f"{rid}-replan-{d+1}"
        if nid not in existing:
            b=t.get("bukova","")
            additions.append({
              "task_id":nid,"canonical_entry_id":t.get("canonical_entry_id"),"bukova":b,
              "status":"PENDING","priority":"replan","track":"BUKOVY_FIRST",
              "created_at":now,"attempt":0,"max_attempts":MAX_ATTEMPTS_PER_TASK,
              "queries":rotated_queries(b),"reason":reason,"parent_task_id":rid,
              "replan_depth":d+1
            })
            existing.add(nid)
    q["tasks"].extend(additions); q["updated_at"]=now
    q["replanned_count"]=q.get("replanned_count",0)+len(additions)
    q["queue_health"]={"policy":"bounded-multi-rotation-replan","max_replan_depth":MAX_REPLAN_DEPTH,
                       "max_attempts_per_task":MAX_ATTEMPTS_PER_TASK,"updated_at":now,
                       "new_replans":len(additions)}
    json.dump(q,open(queue_path,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
    print(json.dumps({"status":"PASS","evidence":"MEASURED","new_replans":len(additions)},ensure_ascii=False))
if __name__=="__main__": raise SystemExit(main())
