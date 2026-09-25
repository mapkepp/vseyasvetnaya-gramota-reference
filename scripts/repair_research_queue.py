#!/usr/bin/env python3
import json
import pathlib
import re
import sys
from datetime import datetime, timezone

MAX_REPLAN_DEPTH = 3
REPLENISH_PER_CYCLE = 4
MAX_ROTATION_GENERATIONS = 2

def depth(task_id):
    return len(re.findall(r"-replan-1", str(task_id)))

def slug(value):
    s = re.sub(r"[^\w\-]+", "-", str(value).strip().casefold(), flags=re.UNICODE)
    return s.strip("-")[:60] or "bukova"

def iso_or_empty(task):
    return str(task.get("created_at") or "")

def main():
    path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "data/research/autonomous-queue.json")
    canonical_path = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "data/bukovy.json")
    q = json.loads(path.read_text("utf-8"))
    canonical = json.loads(canonical_path.read_text("utf-8"))
    now = datetime.now(timezone.utc).isoformat()

    exhausted = []
    for t in q.get("tasks", []):
        if t.get("status") == "PENDING" and depth(t.get("task_id", "")) >= MAX_REPLAN_DEPTH:
            t["status"] = "EXHAUSTED"
            t["exhausted_at"] = now
            t["exhausted_reason"] = "max_replan_depth_reached"
            exhausted.append(t.get("task_id"))

    pending_before = sum(1 for t in q.get("tasks", []) if t.get("status") == "PENDING")
    additions = []
    if pending_before == 0:
        by_name = {}
        for t in q.get("tasks", []):
            by_name.setdefault(t.get("bukova", ""), []).append(t)
        canonical_names = [e.get("name") for e in canonical.get("entries", []) if e.get("name")]

        candidates = []
        for name in canonical_names:
            rows = by_name.get(name, [])
            rotations = [t for t in rows if str(t.get("task_id", "")).startswith("rotation-")]
            rotation_count = len(rotations)
            if rotation_count >= MAX_ROTATION_GENERATIONS:
                continue
            latest = max((iso_or_empty(t) for t in rows), default="")
            candidates.append((rotation_count, len(rows), latest, name))

        candidates.sort()
        generation_now = now.replace(":", "").replace("-", "").replace("+00.00", "Z").replace(".", "")
        for rotation_count, total_count, latest, name in candidates[:REPLENISH_PER_CYCLE]:
            gen = rotation_count + 1
            tid = f"rotation-{slug(name)}-{gen}"
            if any(t.get("task_id") == tid for t in q.get("tasks", [])):
                continue
            additions.append({
                "task_id": tid,
                "bukova": name,
                "status": "PENDING",
                "priority": "rotation",
                "created_at": now,
                "generation": gen,
                "queries": [
                    f'"{name}" Букова практика источник',
                    f'"{name}" Букова "нанес" опыт',
                    f'"{name}" Букова "результат" опыт',
                    f'"{name}" Букова "применял" опыт',
                    f'"{name}" Букова отзыв практика'
                ],
                "reason": "queue_replenishment",
                "generation_stamp": generation_now
            })
    q["tasks"].extend(additions)
    pending_after = sum(1 for t in q.get("tasks", []) if t.get("status") == "PENDING")
    q["queue_health"] = {
        "policy": "bounded-replan-with-rotation",
        "max_replan_depth": MAX_REPLAN_DEPTH,
        "max_rotation_generations": MAX_ROTATION_GENERATIONS,
        "replenish_per_cycle": REPLENISH_PER_CYCLE,
        "repaired_at": now,
        "exhausted_this_run": len(exhausted),
        "replenished_this_run": len(additions),
        "pending_before": pending_before,
        "pending_after": pending_after
    }
    q["updated_at"] = now
    path.write_text(json.dumps(q, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "evidence": "MEASURED",
        "max_replan_depth": MAX_REPLAN_DEPTH,
        "max_rotation_generations": MAX_ROTATION_GENERATIONS,
        "exhausted": len(exhausted),
        "replenished": len(additions),
        "replenished_bukovy": [x["bukova"] for x in additions],
        "pending_before": pending_before,
        "pending_after": pending_after
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    raise SystemExit(main())
