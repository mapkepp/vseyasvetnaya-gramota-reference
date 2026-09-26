#!/usr/bin/env python3
import json, os, urllib.request, urllib.parse
from datetime import datetime, timezone
from pathlib import Path
REPO = "mapkepp/vseyasvetnaya-gramota-reference"
TOKEN = os.environ["GITHUB_TOKEN"]
ROOT = Path("data/research/run-history")
def api(path):
    req = urllib.request.Request("https://api.github.com" + path, headers={"Authorization":"Bearer "+TOKEN,"Accept":"application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
def normalize(x):
    started=x.get("run_started_at") or x.get("created_at"); finished=x.get("updated_at") if x.get("status")=="completed" else None; duration=None
    if started and finished:
        try: duration=max(0,(datetime.fromisoformat(finished.replace("Z","+00:00"))-datetime.fromisoformat(started.replace("Z","+00:00"))).total_seconds())
        except Exception: pass
    return {"run_id":x.get("id"),"run_number":x.get("run_number"),"process":x.get("name") or x.get("display_title") or "Процесс","status":x.get("status") or "unknown","conclusion":x.get("conclusion"),"branch":x.get("head_branch") or "unknown","workflow":x.get("path"),"commit":x.get("head_sha"),"started_at":started,"finished_at":finished,"duration_seconds":duration,"created_at":x.get("created_at"),"updated_at":x.get("updated_at"),"url":x.get("html_url"),"observed_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z")}
records={}
for branch in ("main","dev"):
    data=api("/repos/%s/actions/runs?per_page=100&branch=%s"%(REPO,urllib.parse.quote(branch)))
    for raw in data.get("workflow_runs",[]):
        rec=normalize(raw)
        if rec["run_id"] is not None: records[str(rec["run_id"])]=rec
for p in ROOT.glob("*/*/*/*.json"):
    try:
        for rec in json.loads(p.read_text(encoding="utf-8")):
            if rec.get("run_id") is not None: records.setdefault(str(rec["run_id"]),rec)
    except Exception: pass
shards={}
for rec in records.values():
    started=rec.get("started_at") or rec.get("created_at") or rec.get("observed_at")
    dt=datetime.fromisoformat(started.replace("Z","+00:00")); key=(dt.strftime("%Y"),dt.strftime("%m"),dt.strftime("%d"),rec.get("branch") or "unknown")
    shards.setdefault(key,{})[str(rec["run_id"])]=rec
for key,vals in shards.items():
    path=ROOT.joinpath(*key[:-1],key[-1]+".json"); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(sorted(vals.values(),key=lambda r:r.get("started_at") or r.get("created_at") or "",reverse=True),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
all_records=sorted(records.values(),key=lambda r:r.get("started_at") or r.get("created_at") or "",reverse=True)
(ROOT/"index.json").write_text(json.dumps({"schema_version":"1.0","generated_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),"count":len(all_records),"latest":all_records[:300]},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("RUN_HISTORY records=%d"%len(all_records))
