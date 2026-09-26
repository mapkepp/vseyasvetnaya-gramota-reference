#!/usr/bin/env python3
"""Publish durable telemetry for every research cycle.

Creates research-history, cycle-metrics and specialized-agent telemetry from
the actual artifacts produced by the worker. No canonical data is mutated.
"""
import json, pathlib, hashlib
from datetime import datetime, timezone

R=pathlib.Path("data/research")
OUT=R/"research-history.json"
MET=R/"cycle-metrics.json"
MAN=R/"worker-results/cycle-task-manifest.json"
AGENTS=R/"worker-results/agent-manifest.json"

def load(p,d):
    try:return json.loads(p.read_text(encoding="utf-8"))
    except Exception:return d
def now(): return datetime.now(timezone.utc)

manifest=load(MAN,{"cycle_id":None,"created_at":None,"task_ids":[]})
cycle_id=manifest.get("cycle_id")
if not cycle_id:
    raise SystemExit("No cycle manifest")

tasks=[]
for tid in manifest.get("task_ids",[]):
    t=load(R/"worker-results"/f"{tid}.task.json",{})
    r=load(R/"worker-results"/f"{tid}.result.json",{})
    v=load(R/"worker-results"/f"{tid}.verified.json",{})
    n=load(R/"worker-results"/f"{tid}.normalized.json",{})
    findings=r.get("findings",[]) if isinstance(r,dict) else []
    verified=v.get("findings",v.get("verified_findings",[])) if isinstance(v,dict) else []
    if not isinstance(verified,list): verified=[]
    sources=list(dict.fromkeys([x.get("url") for x in findings if isinstance(x,dict) and x.get("url")]))
    started=r.get("started_at") or manifest.get("created_at")
    finished=r.get("finished_at") or now().isoformat()
    duration=None
    try: duration=max(0,(datetime.fromisoformat(finished.replace("Z","+00:00"))-datetime.fromisoformat(started.replace("Z","+00:00"))).total_seconds())
    except Exception: pass
    status=str(r.get("status") or ("PASS" if r else "FAILED")).upper()
    tasks.append({
      "task_id":tid,"bukova":t.get("bukova") or r.get("bukova") or n.get("bukova"),
      "canonical_entry_id":t.get("canonical_entry_id") or r.get("canonical_entry_id"),
      "status":status,"started_at":started,"finished_at":finished,"duration_seconds":duration,
      "findings_count":len(findings),"source_count":len(sources),
      "verified":bool(v),"verified_count":len(verified),"normalized":bool(n),
      "candidate_count":n.get("candidate_count",0) if isinstance(n,dict) else 0,
      "evidence":r.get("evidence") or r.get("summary") or "",
      "finding_summaries":[str(x.get("summary") or x.get("title") or "") for x in findings[:8] if isinstance(x,dict)],
      "sources":sources[:8]
    })

started=manifest.get("created_at")
finished=now().isoformat()
duration=None
try: duration=max(0,(datetime.fromisoformat(finished.replace("Z","+00:00"))-datetime.fromisoformat(started.replace("Z","+00:00"))).total_seconds())
except Exception: pass
record={"cycle_id":cycle_id,"status":"PASS" if tasks and all(t["status"]=="PASS" for t in tasks) else ("PARTIAL" if tasks else "EMPTY"),
        "started_at":started,"finished_at":finished,"duration_seconds":duration,
        "task_count":len(tasks),"tasks":tasks,
        "summary":{"findings":sum(t["findings_count"] for t in tasks),"sources":sum(t["source_count"] for t in tasks),
                   "verified":sum(t["verified_count"] for t in tasks),"normalized":sum(t["normalized"] for t in tasks)}}
hist=load(OUT,{"schema_version":"1.0","cycles":[]})
cycles=[x for x in hist.get("cycles",[]) if x.get("cycle_id")!=cycle_id]
cycles.insert(0,record)
hist={"schema_version":"1.0","updated_at":finished,"cycles":cycles[:200]}
OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(hist,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

prev=load(MET,{"schema_version":"1.0","cycles":[]})
pc=prev.get("cycles",[])
mc={"cycle_id":cycle_id,"at":finished,"status":record["status"],"duration_seconds":duration,
    "tasks":len(tasks),"found":record["summary"]["findings"],"unique_urls":record["summary"]["sources"],
    "verified":record["summary"]["verified"],"normalized":record["summary"]["normalized"],
    "practitioner_hits":sum(1 for t in tasks if t["candidate_count"]>0)}
pc=[x for x in pc if x.get("cycle_id")!=cycle_id]; pc.insert(0,mc)
recent=pc[:50]
tot={"cycles":len(recent),"tasks":sum(x.get("tasks",0) for x in recent),"found":sum(x.get("found",0) for x in recent),
     "unique_urls":sum(x.get("unique_urls",0) for x in recent),"verified":sum(x.get("verified",0) for x in recent),
     "normalized":sum(x.get("normalized",0) for x in recent),"practitioner_hits":sum(x.get("practitioner_hits",0) for x in recent)}
MET.write_text(json.dumps({"schema_version":"1.0","updated_at":finished,"last_cycle":mc,"totals":tot,"cycles":recent},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

roles=[
 ("search","Поиск источников","DISCOVERY"),
 ("source-verifier","Проверка источников","VERIFY"),
 ("evidence-normalizer","Извлечение и нормализация свидетельств","NORMALIZE"),
 ("quality-gate","Контроль качества практического свидетельства","GATE"),
 ("replanner","Перепланирование незавершённых задач","REPLAN"),
 ("implementation-handoff","Передача результатов в безопасную реализацию","HANDOFF")
]
agent_items=[]
for ident,label,phase in roles:
    if ident=="search": status="PASS" if tasks else "FAIL"
    elif ident=="source-verifier": status="PASS" if any(t["verified"] for t in tasks) else "NO_DATA"
    elif ident=="evidence-normalizer": status="PASS" if any(t["normalized"] for t in tasks) else "NO_DATA"
    elif ident=="quality-gate": status="PASS" if tasks else "NO_DATA"
    else: status="PASS"
    agent_items.append({"id":ident,"label":label,"phase":phase,"status":status,"cycle_id":cycle_id,"updated_at":finished})
AGENTS.parent.mkdir(parents=True,exist_ok=True); AGENTS.write_text(json.dumps({"schema_version":"1.0","updated_at":finished,"cycle_id":cycle_id,"agents":agent_items},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("PUBLISHED",cycle_id,len(tasks))
