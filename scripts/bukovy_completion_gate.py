#!/usr/bin/env python3
"""Create a bounded Bukovy-first completion/readiness surface.

This never edits canonical Bukovy data. It measures the canonical catalog, the
practical-evidence ledger, and the autonomous queue so the research conveyor
has one auditable source of truth for what still needs work.
"""
import json, pathlib
from datetime import datetime, timezone

ROOT=pathlib.Path(__file__).resolve().parents[1]
BUKOVY=ROOT/"data/bukovy.json"
COVERAGE=ROOT/"data/practical-coverage.json"
QUEUE=ROOT/"data/research/autonomous-queue.json"
OUT=ROOT/"data/research/bukovy-research-status.json"

def load(p, default):
    try: return json.loads(p.read_text("utf-8"))
    except Exception: return default

def main():
    buk=load(BUKOVY, {"entries":[]})
    cov=load(COVERAGE, {"entries":[]})
    q=load(QUEUE, {"tasks":[]})
    entries=buk.get("entries", [])
    coverage={x.get("entry_id"):x for x in cov.get("entries",[])}
    tasks={x.get("canonical_entry_id"):x for x in q.get("tasks",[]) if x.get("task_id","").startswith("bukova-core-")}
    rows=[]; counts={}
    for e in entries:
        eid=e.get("entry_id"); c=coverage.get(eid,{}); t=tasks.get(eid,{})
        state=t.get("status","MISSING"); practical=c.get("status","source_description_only")
        counts[practical]=counts.get(practical,0)+1
        rows.append({"entry_id":eid,"name":e.get("name"),"queue_status":state,
          "priority":t.get("priority"),"practical_status":practical,
          "direct_practice_count":c.get("direct_practice_count",0),
          "compound_mention_count":c.get("compound_mention_count",0),
          "sources":c.get("sources",[]),
          "needs_research": practical!="direct_practice_found" or state not in ("DONE","EXHAUSTED")})
    payload={"schema_version":"1.0","updated_at":datetime.now(timezone.utc).isoformat(),
      "focus":"BUKOVY_FIRST","canonical_count":len(entries),"queue_core_task_count":len(tasks),
      "coverage_counts":counts,
      "queue_counts":{"pending":sum(x["queue_status"]=="PENDING" for x in rows),
        "done":sum(x["queue_status"]=="DONE" for x in rows),
        "exhausted":sum(x["queue_status"]=="EXHAUSTED" for x in rows),
        "missing":sum(x["queue_status"]=="MISSING" for x in rows)},
      "rules":{"practical_application_never_inferred_from_description":True,
        "compound_practice_never_attributed_to_component":True,
        "canonical_mutation_requires_review":True,"unknown_is_not_treated_as_negative":True},
      "entries":rows}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n","utf-8")
    print(json.dumps({"canonical_count":len(entries),"queue_core_task_count":len(tasks),
      "coverage_counts":counts},ensure_ascii=False))
if __name__=="__main__": main()
