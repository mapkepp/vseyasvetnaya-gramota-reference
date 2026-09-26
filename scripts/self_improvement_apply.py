#!/usr/bin/env python3
"""Apply only deterministic, bounded self-improvements.

AI never writes executable source here. This stage may change operational
configuration/queue priorities based on measured telemetry and records exactly
what it changed.
"""
import json, pathlib
from datetime import datetime, timezone

ROOT=pathlib.Path(".")
STATUS=ROOT/"data/research/worker-status.json"
QUEUE=ROOT/"data/research/autonomous-queue.json"
PLAN=ROOT/"data/research/self-improvement.json"
OUT=ROOT/"data/research/self-improvement-application.json"

def load(p,d):
    try:return json.loads(p.read_text("utf-8"))
    except Exception:return d

def main():
    now=datetime.now(timezone.utc).isoformat()
    s=load(STATUS,{})
    q=load(QUEUE,{"tasks":[]})
    plan=load(PLAN,{})
    changes=[]
    experience=load(ROOT/"data/research/system-experience.json",{})
    lessons=experience.get("last_lessons",[]) or []
    if lessons:
        changes.append({"change":"apply_system_experience","count":len(lessons),"lessons":lessons[:10],"reason":"previous cycle lessons are inputs to this bounded improvement cycle"})
    pending=[t for t in q.get("tasks",[]) if t.get("status")=="PENDING"]
    failed=[t for t in q.get("tasks",[]) if t.get("status")=="FAILED"]

    # Safe policy: keep one Actions job and six internal agents.
    policy={"github_actions_jobs":1,"parallel_agents":6,"external_ai":"conditional"}
    if pending and len(pending)>=6:
        changes.append({"change":"maintain_parallelism","value":6,"reason":"queue has enough pending work"})
    if failed:
        changes.append({"change":"failed_tasks_visible_to_replanner","count":len(failed),"reason":"replan stage can regenerate weak tasks"})
    if not pending:
        changes.append({"change":"idle_state","value":"WAIT_FOR_QUEUE","reason":"no pending tasks; do not spawn empty agents"})

    result={"schema_version":"1.0","updated_at":now,"status":"PASS",
            "mode":"BOUNDED_AUTONOMOUS","policy":policy,
            "changes":changes,"plan_status":plan.get("status"),
            "experience":{"enabled":bool(experience.get("learning_policy",{}).get("enabled",False)),"lessons_considered":len(lessons)},
            "safety":["no source-code self-modification","no arbitrary shell from AI","no canonical-data mutation",
                      "no additional GitHub jobs","external AI only on low coverage"]}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))

if __name__=="__main__": main()
