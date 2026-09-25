#!/usr/bin/env python3
"""Measure research-cycle yield so self-improvement can learn from outcomes."""
import json, pathlib, statistics
from datetime import datetime, timezone
ROOT=pathlib.Path("data/research/worker-results")
OUT=pathlib.Path("data/research/cycle-metrics.json")
def load(p):
    try:return json.loads(p.read_text("utf-8"))
    except Exception:return {}
def main():
    m=load(ROOT/"cycle-task-manifest.json")
    rows=[]
    for tid in m.get("task_ids",[]):
        r=load(ROOT/(tid+".result.json"))
        v=load(ROOT/(tid+".verified.json"))
        s=load(ROOT/(tid+".specialists.json"))
        findings=r.get("findings",r.get("results",[]))
        if not isinstance(findings,list): findings=[]
        urls={x.get("url") for x in findings if isinstance(x,dict) and x.get("url")}
        verified=v.get("verified",v.get("findings",[]))
        if not isinstance(verified,list): verified=[]
        roles=s.get("roles",[]) if isinstance(s,dict) else []
        rows.append({
            "task_id":tid,"found":len(findings),"unique_urls":len(urls),
            "verified":len(verified),"specialist_evidence":sum(int(x.get("evidence_count",0) or 0) for x in roles if isinstance(x,dict)),
            "practitioner_hits":next((int(x.get("evidence_count",0) or 0) for x in roles if x.get("role")=="practitioner"),0)
        })
    totals={k:sum(x[k] for x in rows) for k in ("found","unique_urls","verified","specialist_evidence","practitioner_hits")}
    metrics={"schema_version":"1.0","updated_at":datetime.now(timezone.utc).isoformat(),
             "cycle_id":m.get("cycle_id"),"tasks":rows,"totals":totals,
             "yield":{"verified_per_url":round(totals["verified"]/max(1,totals["unique_urls"]),4),
                      "practitioner_per_task":round(totals["practitioner_hits"]/max(1,len(rows)),4)}}
    OUT.write_text(json.dumps(metrics,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(metrics,ensure_ascii=False))
if __name__=="__main__":main()
