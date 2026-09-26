#!/usr/bin/env python3
import json, os, pathlib
from datetime import datetime, timezone

ROOT=pathlib.Path(".")
OUT=ROOT/"data/research"
HIST=OUT/"research-history.json"
RESULTS=OUT/"worker-results"
manifest_path=RESULTS/"cycle-task-manifest.json"
if not manifest_path.exists():
    raise SystemExit("cycle manifest missing")
manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
cycle_id=manifest["cycle_id"]
started=manifest.get("created_at") or datetime.now(timezone.utc).isoformat()
ended=datetime.now(timezone.utc).isoformat()

def read(name, default=None):
    p=RESULTS/name
    if not p.exists(): return default
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return default

def iso_epoch(v):
    try: return datetime.fromisoformat(v.replace("Z","+00:00")).timestamp()
    except Exception: return None

tasks=[]
for tid in manifest.get("task_ids",[]):
    task=read(tid+".task.json",{}) or {}
    result=read(tid+".result.json",{}) or {}
    verified=read(tid+".verified.json",{}) or {}
    normalized=read(tid+".normalized.json",{}) or {}
    runtime=read(tid+".runtime.json",{}) or {}
    ts=runtime.get("started_at") or started
    te=runtime.get("finished_at") or result.get("generated_at") or ended
    a,b=iso_epoch(ts),iso_epoch(te)
    findings=result.get("findings") or []
    sources=[]
    for f in findings:
        for s in f.get("sources",[]) or []:
            if s.get("url") and s["url"] not in sources: sources.append(s["url"])
    tasks.append({
        "task_id":tid,
        "canonical_entry_id":task.get("canonical_entry_id"),
        "bukova":task.get("bukova"),
        "priority":task.get("priority"),
        "goal":task.get("goal") or task.get("objective") or "Исследование практического применения и подтверждений",
        "status":result.get("status") or ("DONE" if result else "NO_RESULT"),
        "evidence":result.get("evidence"),
        "started_at":ts,
        "finished_at":te,
        "duration_seconds":round(max(0,b-a),3) if a is not None and b is not None else None,
        "attempt":task.get("attempt"),
        "queries":result.get("queries") or task.get("queries") or [],
        "findings_count":len(findings),
        "verified":bool(verified),
        "normalized":bool(normalized),
        "sources":sources[:50],
        "source_count":len(sources),
        "finding_summaries":[f.get("claim") for f in findings[:30] if f.get("claim")],
        "diagnostics":result.get("diagnostics",[])[:20],
        "error":result.get("error")
    })

a,b=iso_epoch(started),iso_epoch(ended)
entry={
    "schema_version":"2.0",
    "cycle_id":cycle_id,
    "run_id":os.environ.get("GITHUB_RUN_ID"),
    "run_number":os.environ.get("GITHUB_RUN_NUMBER"),
    "workflow":"Autonomous research worker",
    "event":os.environ.get("GITHUB_EVENT_NAME"),
    "branch":os.environ.get("GITHUB_REF_NAME","dev"),
    "commit":os.environ.get("GITHUB_SHA"),
    "started_at":started,
    "finished_at":ended,
    "duration_seconds":round(max(0,b-a),3) if a is not None and b is not None else None,
    "selected_tasks":len(tasks),
    "tasks":tasks
}
history={"schema_version":"2.0","updated_at":ended,"cycles":[]}
if HIST.exists():
    try: history=json.loads(HIST.read_text(encoding="utf-8"))
    except Exception: pass
cycles=[x for x in history.get("cycles",[]) if x.get("cycle_id")!=cycle_id]
cycles.insert(0,entry)
history["cycles"]=cycles[:500]
history["updated_at"]=ended
HIST.write_text(json.dumps(history,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(f"Recorded cycle {cycle_id}: {len(tasks)} tasks; history={len(history['cycles'])}")
