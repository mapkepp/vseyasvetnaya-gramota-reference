#!/usr/bin/env python3
import json, pathlib, sys
from datetime import datetime, timezone

queue_path, manifest_path, active_path, status_path = map(pathlib.Path, sys.argv[1:5])
queue=json.load(queue_path.open(encoding="utf-8"))
manifest=json.load(manifest_path.open(encoding="utf-8"))
by_id={t["task_id"]:t for t in queue.get("tasks",[])}
now=datetime.now(timezone.utc).isoformat()
active=[]
for task_id in manifest.get("task_ids",[]):
    t=by_id.get(task_id,{})
    active.append({
        "task_id":task_id,"bukova":t.get("bukova"),"canonical_entry_id":t.get("canonical_entry_id"),
        "status":"RUNNING","phase":"поиск источников","started_at":now,"finished_at":None,
        "expected":"Найти независимые свидетельства практического применения этой Буковы, зафиксировать источник, действие практика и наблюдаемый результат.",
        "queries":t.get("queries",[])
    })
active_path.write_text(json.dumps({"schema_version":"1.1","cycle_id":manifest.get("cycle_id"),"updated_at":now,"active_tasks":active},ensure_ascii=False,indent=2),encoding="utf-8")
status_path.write_text(json.dumps({"schema_version":"1.1","updated_at":now,"cycle_id":manifest.get("cycle_id"),"worker":"github-public-web","worker_status":"RUNNING","phase":"SEARCH","selected_tasks":len(active),"active_tasks":active,"execution":"MEASURED"},ensure_ascii=False,indent=2),encoding="utf-8")
print("LIVE_STATUS_PUBLISHED",len(active),now)
