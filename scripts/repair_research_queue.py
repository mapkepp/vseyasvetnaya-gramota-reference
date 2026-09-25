#!/usr/bin/env python3
import json, pathlib, re, sys
from datetime import datetime, timezone
MAX_REPLAN_DEPTH=3
REPLENISH_PER_CYCLE=4
def depth(task_id): return len(re.findall(r"-replan-1",str(task_id)))
def slug(v):
    return re.sub(r"[^\w\-]+","-",str(v).strip().casefold(),flags=re.UNICODE).strip("-")[:50] or "entry"
def main():
    qp=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else "data/research/autonomous-queue.json")
    cp=pathlib.Path(sys.argv[2] if len(sys.argv)>2 else "data/bukovy.json")
    q=json.loads(qp.read_text("utf-8")); c=json.loads(cp.read_text("utf-8"))
    entries=[e for e in c.get("entries",[]) if e.get("name") and e.get("entry_id")]
    by_name={}; by_id={}
    for e in entries: by_name.setdefault(e["name"],[]).append(e["entry_id"]); by_id[e["entry_id"]]=e
    used=set()
    for t in q.get("tasks",[]):
        if not t.get("canonical_entry_id"):
            ids=by_name.get(t.get("bukova"),[])
            if len(ids)==1: t["canonical_entry_id"]=ids[0]
        tid=t.get("task_id") or "task"
        if tid in used:
            n=2; base=tid
            while f"{base}--{n}" in used:n+=1
            t["task_id"]=f"{base}--{n}"
        used.add(t["task_id"])
    now=datetime.now(timezone.utc).isoformat()
    for t in q.get("tasks",[]):
        if t.get("status")=="PENDING" and depth(t.get("task_id",""))>=MAX_REPLAN_DEPTH:
            t["status"]="EXHAUSTED"; t["exhausted_at"]=now
    pending={t.get("canonical_entry_id") or t.get("bukova") for t in q.get("tasks",[]) if t.get("status")=="PENDING"}
    existing={t.get("task_id") for t in q.get("tasks",[])}
    additions=[]
    for e in entries:
        if len(pending)>=REPLENISH_PER_CYCLE: break
        if e["entry_id"] in pending: continue
        tid=f"rotation-{slug(e['entry_id'])}-1"
        if tid in existing: continue
        additions.append({"task_id":tid,"canonical_entry_id":e["entry_id"],"bukova":e["name"],"status":"PENDING","priority":"rotation","created_at":now,
          "queries":[f'"{e["name"]}" Букова практика источник',f'"{e["name"]}" Букова "нанес" опыт',f'"{e["name"]}" Букова "результат" опыт',f'"{e["name"]}" Букова "применял" опыт'],"reason":"queue_replenishment"})
        pending.add(e["entry_id"]); existing.add(tid)
    q["tasks"].extend(additions); q["updated_at"]=now
    q["queue_health"]={"policy":"bounded-replan-with-entry-id-rotation","max_replan_depth":MAX_REPLAN_DEPTH,"replenished_this_run":len(additions),"pending_after":sum(t.get("status")=="PENDING" for t in q["tasks"]),"repaired_at":now}
    qp.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n","utf-8")
if __name__=="__main__": main()
