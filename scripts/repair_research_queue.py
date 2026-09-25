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
    return s.strip("-")[:50] or "bukova"

def hydrate_entry_ids(tasks, canonical_entries):
    by_name = {}
    for e in canonical_entries:
        by_name.setdefault(e.get("name"), []).append(e.get("entry_id"))
    used = set()
    for t in tasks:
        if t.get("canonical_entry_id"):
            used.add(t["canonical_entry_id"])
    for t in tasks:
        if t.get("canonical_entry_id"):
            continue
        ids = by_name.get(t.get("bukova"), [])
        if len(ids) == 1:
            t["canonical_entry_id"] = ids[0]
            used.add(ids[0])
        elif ids:
            # Legacy queue items with duplicated display names are assigned
            # deterministically to the first still-unassigned canonical entry.
            pick = next((x for x in ids if x not in used), ids[0])
            t["canonical_entry_id"] = pick
            used.add(pick)

def main():
    queue_path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "data/research/autonomous-queue.json")
    canonical_path = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "data/bukovy.json")
    q = json.loads(queue_path.read_text("utf-8"))
    canonical = json.loads(canonical_path.read_text("utf-8"))
    entries = [e for e in canonical.get("entries", []) if e.get("name") and e.get("entry_id")]
    now = datetime.now(timezone.utc).isoformat()

    hydrate_entry_ids(q.get("tasks", []), entries)

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
        by_entry = {}
        for t in q.get("tasks", []):
            by_entry.setdefault(t.get("canonical_entry_id"), []).append(t)

        candidates = []
        for e in entries:
            eid, name = e["entry_id"], e["name"]
            rows = by_entry.get(eid, [])
            rotations = [t for t in rows if str(t.get("task_id", "")).startswith("rotation-")]
            rotation_count = len(rotations)
            if rotation_count >= MAX_ROTATION_GENERATIONS:
                continue
            latest = max((str(t.get("created_at") or "") for t in rows), default="")
            candidates.append((rotation_count, len(rows), latest, eid, name))

        candidates.sort()
        for rotation_count, total_count, latest, eid, name in candidates[:REPLENISH_PER_CYCLE]:
            gen = rotation_count + 1
            tid = f"rotation-{slug(eid)}-{gen}"
            if any(t.get("task_id") == tid for t in q.get("tasks", [])):
                continue
            additions.append({
                "task_id": tid,
                "canonical_entry_id": eid,
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
                "reason": "queue_replenishment"
            })

    q["tasks"].extend(additions)
    pending_after = sum(1 for t in q.get("tasks", []) if t.get("status") == "PENDING")
    q["queue_health"] = {
        "policy": "bounded-replan-with-entry-id-rotation",
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
    queue_path.write_text(json.dumps(q, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "evidence": "MEASURED",
        "exhausted": len(exhausted),
        "replenished": len(additions),
        "replenished_entries": [{"entry_id":x["canonical_entry_id"],"bukova":x["bukova"]} for x in additions],
        "pending_before": pending_before,
        "pending_after": pending_after
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    raise SystemExit(main())
