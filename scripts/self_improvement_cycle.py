#!/usr/bin/env python3
"""Bounded self-improvement planner.

It learns from measurable worker telemetry, proposes concrete improvements,
and applies only deterministic low-risk changes. AI output is advisory and
cannot directly execute arbitrary code or rewrite canonical data.
"""
import json, pathlib, subprocess
from datetime import datetime, timezone

ROOT=pathlib.Path(".")
STATUS=ROOT/"data/research/worker-status.json"
QUEUE=ROOT/"data/research/autonomous-queue.json"
OUT=ROOT/"data/research/self-improvement.json"

def load(p, default):
    try:return json.loads(p.read_text("utf-8"))
    except Exception:return default

def main():
    now=datetime.now(timezone.utc).isoformat()
    s=load(STATUS,{})
    q=load(QUEUE,{"tasks":[]})
    pending=sum(1 for t in q.get("tasks",[]) if t.get("status")=="PENDING")
    failed=sum(1 for t in q.get("tasks",[]) if t.get("status")=="FAILED")
    proposals=[]
    if s.get("selected_tasks",0)==0 and pending:
        proposals.append({"id":"resume-pending","action":"increase_scheduler_frequency","reason":"pending tasks exist but last cycle selected none","safe":True})
    if failed:
        proposals.append({"id":"failed-task-rotation","action":"route_failed_tasks_to_replan","reason":f"{failed} failed tasks are present","safe":True})
    if s.get("review_queue_count",0)>0:
        proposals.append({"id":"review-evidence","action":"prioritize_human_review_queue","reason":"verified evidence still needs review","safe":True})
    proposals.append({"id":"cap-external-escalation","action":"use_external_ai_only_on_low_coverage","reason":"avoid duplicate search/model cost","safe":True})
    state={"schema_version":"1.0","updated_at":now,"status":"PASS","mode":"BOUNDED_AUTONOMOUS",
           "inputs":{"pending":pending,"failed":failed,"last_cycle":s.get("cycle_id")},
           "proposals":proposals,
           "policy":["no arbitrary code execution","no canonical-data mutation by AI","bounded changes only",
                     "prefer free/local providers","escalate external AI only when evidence coverage is weak"]}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(state,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
