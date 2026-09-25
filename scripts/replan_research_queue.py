#!/usr/bin/env python3
import json,sys,pathlib,re
from datetime import datetime,timezone
MAX_REPLAN_DEPTH=3
def depth(x): return len(re.findall(r"-replan-1",str(x)))
def main():
    qp=pathlib.Path(sys.argv[1]); rd=pathlib.Path(sys.argv[2]); mp=pathlib.Path(sys.argv[3]) if len(sys.argv)>3 else rd/"cycle-task-manifest.json"
    q=json.load(open(qp,encoding="utf-8")); m=json.load(open(mp,encoding="utf-8")) if mp.exists() else {"task_ids":[]}; allowed=set(m.get("task_ids",[])); existing={t.get("task_id") for t in q.get("tasks",[])}; add=[]; now=datetime.now(timezone.utc).isoformat()
    for t in q.get("tasks",[]):
      if t.get("task_id") not in allowed or t.get("status") not in ("DONE","FAILED"): continue
      reason="worker_failed" if t.get("status")=="FAILED" else None
      if not reason:
        v=json.load(open(rd/f'{t["task_id"]}.verified.json',encoding="utf-8")) if (rd/f'{t["task_id"]}.verified.json').exists() else {}
        n=json.load(open(rd/f'{t["task_id"]}.normalized.json',encoding="utf-8")) if (rd/f'{t["task_id"]}.normalized.json').exists() else {}
        if v.get("status")!="PASS": reason="verification_incomplete"
        elif not any(c.get("status")=="READY_FOR_REVIEW" for c in n.get("candidates",[])): reason="normalization_incomplete"
      if not reason: continue
      if depth(t.get("task_id",""))>=MAX_REPLAN_DEPTH: t["status"]="EXHAUSTED";t["exhausted_at"]=now;continue
      nid=t["task_id"]+"-replan-1"
      if nid not in existing:
        b=t.get("bukova",""); add.append({"task_id":nid,"canonical_entry_id":t.get("canonical_entry_id"),"bukova":b,"status":"PENDING","priority":"replan","created_at":now,"parent_task_id":t["task_id"],"reason":reason,"queries":[f'"{b}" практика Букова форум',f'"{b}" "нанес" Букова',f'"{b}" "получил результат"',f'"{b}" "применял" практика']});existing.add(nid)
    q["tasks"].extend(add);q["updated_at"]=now;q["replanned_count"]=q.get("replanned_count",0)+len(add);q["queue_health"]={"policy":"bounded-replan","max_replan_depth":MAX_REPLAN_DEPTH,"new_replans":len(add),"updated_at":now};qp.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n","utf-8")
if __name__=="__main__":main()
