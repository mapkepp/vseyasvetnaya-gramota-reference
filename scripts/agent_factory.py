#!/usr/bin/env python3
"""Create bounded specialist sub-agents for weak research tasks."""
import json, pathlib, sys
from datetime import datetime, timezone

ROLES = [
    ("identity", "Проверить идентичность Буковы и варианты написания."),
    ("practitioner", "Искать конкретные истории применения человеком."),
    ("result", "Извлечь действие и наблюдаемый результат, не подменяя описанием."),
    ("corroboration", "Искать независимое подтверждение найденного свидетельства."),
    ("source_quality", "Проверить автора, дату, первичность и устойчивость источника.")
]

def main():
    out=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else "data/research/worker-results")
    manifest=json.loads((out/"cycle-task-manifest.json").read_text("utf-8"))
    agents=[]
    for tid in manifest.get("task_ids",[]):
        for role,goal in ROLES:
            agents.append({"agent_id":f"{tid}:{role}","task_id":tid,"role":role,"goal":goal,
                           "status":"READY","created_at":datetime.now(timezone.utc).isoformat()})
    (out/"agent-manifest.json").write_text(json.dumps({
        "schema_version":"1.0","bounded":True,"max_agents_per_task":len(ROLES),
        "agents":agents,"created_at":datetime.now(timezone.utc).isoformat()
    },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"PASS","tasks":len(manifest.get("task_ids",[])),"specialist_agents":len(agents)},ensure_ascii=False))

if __name__=="__main__": main()
