#!/usr/bin/env python3
import json
import pathlib
import re
import sys
from datetime import datetime, timezone

MAX_REPLAN_DEPTH = 3

def depth(task_id):
    return len(re.findall(r"-replan-1", str(task_id)))

def main():
    path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "data/research/autonomous-queue.json")
    q = json.loads(path.read_text("utf-8"))
    now = datetime.now(timezone.utc).isoformat()
    changed = []
    exhausted = 0
    for t in q.get("tasks", []):
        if t.get("status") == "PENDING" and depth(t.get("task_id", "")) >= MAX_REPLAN_DEPTH:
            t["status"] = "EXHAUSTED"
            t["exhausted_at"] = now
            t["exhausted_reason"] = "max_replan_depth_reached"
            changed.append(t.get("task_id"))
            exhausted += 1
    pending = sum(1 for t in q.get("tasks", []) if t.get("status") == "PENDING")
    q["queue_health"] = {
        "policy": "bounded-replan",
        "max_replan_depth": MAX_REPLAN_DEPTH,
        "repaired_at": now,
        "exhausted_this_run": exhausted,
        "pending_after_repair": pending,
    }
    q["updated_at"] = now
    path.write_text(json.dumps(q, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS", "evidence": "MEASURED",
        "max_replan_depth": MAX_REPLAN_DEPTH,
        "exhausted": exhausted,
        "changed_task_ids": changed,
        "pending_after_repair": pending
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    raise SystemExit(main())
