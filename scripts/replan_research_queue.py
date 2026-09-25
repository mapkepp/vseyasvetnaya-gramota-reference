#!/usr/bin/env python3
import json,sys
from datetime import datetime,timezone

def main():
 q=json.load(open(sys.argv[1],encoding="utf-8"))
 results_dir=sys.argv[2]
 tasks=q.get("tasks",[])
 existing={t.get("task_id") for t in tasks}
 additions=[]
 for t in tasks:
  if t.get("status")!="DONE": continue
  rid=t.get("task_id")
  try:
   r=json.load(open(f"{results_dir}/{rid}.verified.json",encoding="utf-8"))
  except Exception:
   continue
  if r.get("status")!="PASS":
   n={"task_id":f"{rid}-replan-1","bukova":t.get("bukova"),
      "status":"PENDING","priority":"replan","created_at":datetime.now(timezone.utc).isoformat(),
      "queries":[f'"{t.get("bukova","")}" практика Букова форум',
                 f'"{t.get("bukova","")}" "нанес" Букова',
                 f'"{t.get("bukova","")}" "получил результат"'],
      "reason":"verification_incomplete","parent_task_id":rid}
   if n["task_id"] not in existing:
    additions.append(n); existing.add(n["task_id"])
 q["tasks"].extend(additions)
 q["updated_at"]=datetime.now(timezone.utc).isoformat()
 q["replanned_count"]=q.get("replanned_count",0)+len(additions)
 json.dump(q,open(sys.argv[1],"w",encoding="utf-8"),ensure_ascii=False,indent=2)
 return 0
if __name__=="__main__": raise SystemExit(main())
