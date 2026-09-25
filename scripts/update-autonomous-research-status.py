#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
coverage=json.loads((ROOT/"data/practical-coverage.json").read_text("utf-8"))
histories=json.loads((ROOT/"data/practice/practitioner-histories.json").read_text("utf-8"))
entries=coverage.get("entries",[])

priority={
    "direct_practice_found":0,
    "compound_only":1,
    "source_description_plus_practical_context":2,
    "general_practice_context":3,
    "source_description_only":4,
}

def score(e):
    return (
        priority.get(e.get("status"),9),
        int(e.get("direct_practice_count",0)),
        int(e.get("compound_mention_count",0)),
        e.get("name","")
    )

targets=sorted(entries,key=score)[:16]
now=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
queue={
    "schema_version":"1.0",
    "generated_at":now,
    "project":"vseyasvetnaya-gramota-reference",
    "mode":"autonomous-research-coordinator",
    "rules":{
        "canonical_count":68,
        "do_not_invent_canonical_entries":True,
        "practitioner_story_requires":["identifiable practitioner","specific Bukova or explicitly composite stave","action","reported result","source URL"],
        "compound_effects_are_not_attributed_to_components":True,
        "source_claims_are_not_presented_as_scientific_validation":True
    },
    "tasks":[
        {
            "task_id":f"bukovy-practice-{i+1:02d}",
            "bukova":e.get("name"),
            "entry_id":e.get("entry_id"),
            "status":"PENDING",
            "priority":score(e)[0],
            "queries":[
                f'"{e.get("name")}" "применял" Букова',
                f'"{e.get("name")}" "использовал" Букова',
                f'"{e.get("name")}" "нанес" Букова',
                f'"{e.get("name")}" "получил" Букова'
            ]
        } for i,e in enumerate(targets)
    ]
}
status={
    "schema_version":"1.0",
    "updated_at":now,
    "project":"vseyasvetnaya-gramota-reference",
    "state":"RUNNING",
    "evidence":"MEASURED",
    "catalog_count":coverage.get("catalog_count"),
    "practitioner_history_count":len(histories.get("stories",[])),
    "research_queue_count":len(queue["tasks"]),
    "research_execution":"coordinator_active_external_worker_expected",
    "note":"This job plans and records research work. Evidence-producing workers run through the toolbox supervisor; this workflow does not invent findings.",
    "next_cycle":"hourly"
}
out=ROOT/"data/research"
out.mkdir(parents=True,exist_ok=True)
(out/"autonomous-queue.json").write_text(json.dumps(queue,ensure_ascii=False,indent=2)+"\n","utf-8")
(out/"autonomous-status.json").write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n","utf-8")
print(json.dumps(status,ensure_ascii=False))
