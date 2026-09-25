#!/usr/bin/env python3
import json,sys,pathlib
from datetime import datetime,timezone

def main():
    queue_path=pathlib.Path(sys.argv[1]); results_dir=pathlib.Path(sys.argv[2])
    manifest_path=pathlib.Path(sys.argv[3]) if len(sys.argv)>3 else results_dir/"cycle-task-manifest.json"
    q=json.load(open(queue_path,encoding="utf-8"))
    manifest=json.load(open(manifest_path,encoding="utf-8")) if manifest_path.exists() else {"task_ids":[t.get("task_id") for t in q.get("tasks",[]) if t.get("status")=="DONE"]}
    allowed=set(manifest.get("task_ids",[])); existing={t.get("task_id") for t in q.get("tasks",[])}
    additions=[]
    for t in q.get("tasks",[]):
        rid=t.get("task_id")
        if rid not in allowed or t.get("status")!="DONE": continue
        vf=results_dir/(rid+".verified.json")
        try: r=json.load(open(vf,encoding="utf-8"))
        except Exception: continue
        if r.get("status")!="PASS":
            nid=rid+"-replan-1"
            if nid not in existing:
                additions.append({"task_id":nid,"bukova":t.get("bukova"),"status":"PENDING","priority":"replan",
                  "created_at":datetime.now(timezone.utc).isoformat(),
                  "queries":[f'"{t.get("bukova","")}" практика Букова форум',
                             f'"{t.get("bukova","")}" "нанес" Букова',
                             f'"{t.get("bukova","")}" "получил результат"'],
                  "reason":"verification_incomplete","parent_task_id":rid})
                existing.add(nid)
    q["tasks"].extend(additions); q["updated_at"]=datetime.now(timezone.utc).isoformat()
    q["replanned_count"]=q.get("replanned_count",0)+len(additions)
    json.dump(q,open(queue_path,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
if __name__=="__main__": main()
