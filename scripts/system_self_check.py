#!/usr/bin/env python3
"""Bounded integrity/self-repair controller for the autonomous toolbox.

The controller never mutates main/dev semantics or deletes branches. It repairs only
derived telemetry and generated registries, records every observation/repair as system
experience, and fails closed when a repair would require a human decision.
"""
import json, pathlib, subprocess, re
from datetime import datetime, timezone

ROOT=pathlib.Path(".")
HEALTH=ROOT/"data/research/system-health.json"
EXPERIENCE=ROOT/"data/research/system-experience.json"
REGISTRY=ROOT/"data/research/status-surface-registry.json"
WATCHED_JSON=(ROOT/"data/research", ROOT/"data/toolbox")
WRITER_WORKFLOWS={
    "autonomous-research-worker.yml","toolbox-evolution.yml",
    "autonomous-implementation-workers.yml","branch-intake.yml","branch-archive-cleanup.yml",
    "system-self-repair.yml","rebuild-main-candidate.yml"
}
def now(): return datetime.now(timezone.utc).isoformat()
def run(cmd):
    p=subprocess.run(cmd,capture_output=True,text=True)
    return p.returncode,p.stdout.strip(),p.stderr.strip()
def load(path, default):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except Exception:return default
def check_json():
    bad=[]
    for root in WATCHED_JSON:
        if not root.exists(): continue
        for p in root.rglob("*.json"):
            if p.name=="system-experience.json": continue
            try: json.loads(p.read_text(encoding="utf-8"))
            except Exception as e: bad.append(f"{p}: {e}")
    return bad
def check_python():
    rc,_,err=run(["python3","-m","compileall","-q","scripts"])
    return [] if rc==0 else [err or "compileall failed"]
def check_status_html():
    candidates=[]
    p=ROOT/"research-status.html"
    if p.exists(): candidates.append(p)
    rc,_,_=run(["git","rev-parse","--verify","origin/main"])
    if rc==0:
        rc,out,err=run(["git","show","origin/main:research-status.html"])
        if rc==0:
            t=ROOT/"data/research/.status-main-check.html"
            t.parent.mkdir(parents=True,exist_ok=True); t.write_text(out,encoding="utf-8"); candidates.append(t)
    errors=[]
    for p in candidates:
        s=p.read_text(encoding="utf-8")
        if "staticFallback" not in s: errors.append(f"{p}: missing static maintenance fallback")
        m=re.search(r"<script>([\s\S]*?)</script>",s)
        if not m: errors.append(f"{p}: missing script")
        else:
            q=ROOT/"data/research/.status-script-check.js"; q.write_text(m.group(1),encoding="utf-8")
            rc,_,err=run(["node","--check",str(q)])
            if rc: errors.append(f"{p}: JS syntax: {err}")
    for p in [ROOT/"data/research/.status-main-check.html",ROOT/"data/research/.status-script-check.js"]:
        try:p.unlink()
        except FileNotFoundError:pass
    return errors
def check_writer_serialization():
    bad=[]
    wf=ROOT/".github/workflows"
    for name in WRITER_WORKFLOWS:
        p=wf/name
        if not p.exists(): bad.append(f"missing writer workflow: {name}"); continue
        s=p.read_text(encoding="utf-8")
        if "group: dev-state-writers" not in s or "cancel-in-progress: false" not in s:
            bad.append(f"{name}: missing shared dev-state-writers serialization")
    return bad
def repair_registry():
    p=ROOT/"scripts/sync_status_surfaces.py"
    if not p.exists(): return "blocked: sync_status_surfaces.py missing"
    rc,_,err=run(["python3",str(p)])
    return "repaired: status surface registry regenerated" if rc==0 else f"repair-failed: {err}"
def main():
    issues=[]
    issues += check_json()
    issues += check_python()
    issues += check_status_html()
    issues += check_writer_serialization()
    repairs=[]
    # Derived status data is regenerated every cycle so new surfaces become visible automatically.
    repairs.append(repair_registry())
    status="PASS" if not issues else "REPAIR_NEEDED"
    drift={"status":"UNKNOWN","main_only":None,"dev_only":None}
    rc,out,_=run(["git","rev-list","--left-right","--count","origin/main...HEAD"])
    if rc==0:
        parts=out.split()
        if len(parts)==2:
            drift={"status":"DIVERGED" if parts[0]!="0" and parts[1]!="0" else "ALIGNED_OR_AHEAD","main_only":int(parts[0]),"dev_only":int(parts[1])}
    health={"schema_version":"1.0","updated_at":now(),"status":status,"branch_coherence":drift,
            "issues":issues[:100],"repairs":repairs,"experience_recorded":True,
            "policy":{"fail_closed":True,"protected_branches":["main","dev"],
                      "auto_delete_branches":False,"auto_repair_scope":["generated telemetry","status registry"],
                      "human_review_required":["canonical content","security","ambiguous integration","destructive changes"]}}
    HEALTH.parent.mkdir(parents=True,exist_ok=True)
    HEALTH.write_text(json.dumps(health,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    exp=load(EXPERIENCE,{"schema_version":"1.0","events":[]})
    fp=json.dumps({"status":status,"issues":issues,"repairs":repairs},ensure_ascii=False,sort_keys=True)
    event={"at":now(),"fingerprint":__import__("hashlib").sha256(fp.encode()).hexdigest()[:16],
           "status":status,"issues":issues[:20],"repairs":repairs}
    events=exp.get("events",[])
    if not events or events[-1].get("fingerprint")!=event["fingerprint"] or events[-1].get("status")!=status:
        events.append(event)
    exp["events"]=events[-200:]
    exp["last_success_at"]=event["at"] if status=="PASS" else exp.get("last_success_at")
    exp["last_failure_at"]=event["at"] if status!="PASS" else exp.get("last_failure_at")
    exp["learning_policy"]={"deduplicate":True,"retain_last":200,"learn_from_failures":True}
    EXPERIENCE.write_text(json.dumps(exp,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(health,ensure_ascii=False))
if __name__=="__main__": main()
