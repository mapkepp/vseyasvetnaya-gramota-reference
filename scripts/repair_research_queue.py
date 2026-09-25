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
    return s.strip("-")[:50] or "entry"

def hydrate_entry_ids(tasks, canonical_entries):
    by_name = {}
    for e in canonical_entries:
        by_name.setdefault(e.get("name"), []).append(e.get("entry_id"))
    used = set(t.get("canonical_entry_id") for t in tasks if t.get("canonical_entry_id"))
    for t in tasks:
        if t.get("canonical_entry_id"):
            continue
        ids = by_name.get(t.get("bukova"), [])
        if len(ids) == 1:
            t["canonical_entry_id"] = ids[0]
            used.add(ids[0])
        elif ids:
            pick = next((x for x in ids if x not in used), ids[0])
            t["canonical_entry_id"] = pick
            used.add(pick)

def desired_id(task, used_ids):
    old = str(task.get("task_id") or "")
    eid = task.get("canonical_entry_id")
    if not eid:
        base = old or "task"
    elif old.startswith("rotation-"):
        generation = int(task.get("generation") or 1)
        base = f"rotation-{slug(eid)}-{generation}" + "-replan-1" * depth(old)
    else:
        # Preserve legacy non-rotation identifiers unless they collide.
        base = old

    candidate = base
    n = 2
    while candidate in used_ids:
        candidate = f"{base}--{slug(eid or old)}-{n}"
        n += 1
    return candidate

def normalize_task_ids(tasks):
    used = set()
    mapping = []
    for t in tasks:
        old = t.get("task_id")
        new = desired_id(t, used)
        if new != old:
            mapping.append((old, new, t.get("canonical_entry_id")))
            t["legacy_task_id"] = old
            t["task_id"] = new
        used.add(new)

    for t in tasks:
        parent = t.get("parent_task_id")
        if not parent:
            continue
        eid = t.get("canonical_entry_id")
        match = next((new for old,new,peid in mapping if old == parent and peid == eid), None)
        if match:
            t["parent_task_id"] = match
        else:
            # Safe fallback if the parent identifier was not duplicated.
            match = next((new for old,new,peid in mapping if old == parent), None)
            if match:
                t["parent_task_id"] = match
    return mapping

def supersede_pending_duplicates(tasks, now):
    groups = {}
    for t in tasks:
        if t.get("status") == "PENDING":
            key = t.get("canonical_entry_id") or t.get("bukova") or t.get("task_id")
            groups.setdefault(key, []).append(t)

    superseded = []
    priority = {"replan": 3, "rotation": 2, "normal": 1}
    for key, rows in groups.items():
        if len(rows) <= 1:
            continue
        keep = max(rows, key=lambda t: (
            priority.get(str(t.get("priority") or "normal"), 0),
            depth(t.get("task_id")),
            str(t.get("created_at") or "")
        ))
        for t in rows:
            if t is keep:
                continue
            t["status"] = "SUPERSEDED"
            t["superseded_at"] = now
            t["superseded_by"] = keep.get("task_id")
            t["superseded_reason"] = "duplicate_pending_canonical_entry"
            superseded.append(t.get("task_id"))
    return superseded

def main():
    queue_path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "data/research/autonomous-queue.json")
    canonical_path = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "data/bukovy.json")
    q = json.loads(queue_path.read_text("utf-8"))
    canonical = json.loads(canonical_path.read_text("utf-8"))
    entries = [e for e in canonical.get("entries", []) if e.get("name") and e.get("entry_id")]
    now = datetime.now(timezone.utc).isoformat()

    hydrate_entry_ids(q.get("tasks", []), entries)
    migrated = normalize_task_ids(q.get("tasks", []))

    exhausted = []
    for t in q.get("tasks", []):
        if t.get("status") == "PENDING" and depth(t.get("task_id", "")) >= MAX_REPLAN_DEPTH:
            t["status"] = "EXHAUSTED"
            t["exhausted_at"] = now
            t["exhausted_reason"] = "max_replan_depth_reached"
            exhausted.append(t.get("task_id"))

    superseded = supersede_pending_duplicates(q.get("tasks", []), now)

    pending_tasks = [t for t in q.get("tasks", []) if t.get("status") == "PENDING"]
    pending_entries = set(t.get("canonical_entry_id") or t.get("bukova") or t.get("task_id") for t in pending_tasks)
    needed = max(0, REPLENISH_PER_CYCLE - len(pending_entries))
    additions = []

    if needed:
        by_entry = {}
        for t in q.get("tasks", []):
            by_entry.setdefault(t.get("canonical_entry_id") or t.get("bukova"), []).append(t)

        candidates = []
        for e in entries:
            eid, name = e["entry_id"], e["name"]
            if eid in pending_entries:
                continue
            rows = by_entry.get(eid, [])
            rotations = [t for t in rows if str(t.get("task_id", "")).startswith("rotation-")]
            rotation_count = len(rotations)
            if rotation_count >= MAX_ROTATION_GENERATIONS:
                continue
            latest = max((str(t.get("created_at") or "") for t in rows), default="")
            candidates.append((rotation_count, len(rows), latest, eid, name))

        candidates.sort()
        for rotation_count, total_count, latest, eid, name in candidates[:needed]:
            gen = rotation_count + 1
            tid = f"rotation-{slug(eid)}-{gen}"
            suffix = 2
            while any(t.get("task_id") == tid for t in q.get("tasks", [])) or any(x.get("task_id") == tid for x in additions):
                tid = f"rotation-{slug(eid)}-{gen}--{suffix}"
                suffix += 1
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
            pending_entries.add(eid)

    q["tasks"].extend(additions)
    pending_after = [t for t in q.get("tasks", []) if t.get("status") == "PENDING"]
    distinct_after = len(set(t.get("canonical_entry_id") or t.get("bukova") or t.get("task_id") for t in pending_after))
    duplicate_pending = len(pending_after) - distinct_after

    q["queue_health"] = {
        "policy": "bounded-replan-with-entry-id-rotation",
        "max_replan_depth": MAX_REPLAN_DEPTH,
        "max_rotation_generations": MAX_ROTATION_GENERATIONS,
        "target_distinct_pending": REPLENISH_PER_CYCLE,
        "repaired_at": now,
        "task_ids_migrated": len(migrated),
        "exhausted_this_run": len(exhausted),
        "superseded_this_run": len(superseded),
        "replenished_this_run": len(additions),
        "pending_after": len(pending_after),
        "distinct_pending_entries_after": distinct_after,
        "duplicate_pending_after": duplicate_pending
    }
    q["updated_at"] = now
    queue_path.write_text(json.dumps(q, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status":"PASS","evidence":"MEASURED",
        "task_ids_migrated":len(migrated),
        "exhausted":len(exhausted),
        "superseded":len(superseded),
        "replenished":len(additions),
        "pending_after":len(pending_after),
        "distinct_pending_entries_after":distinct_after,
        "duplicate_pending_after":duplicate_pending
    },ensure_ascii=False,indent=2))

if __name__=="__main__":
    raise SystemExit(main())
