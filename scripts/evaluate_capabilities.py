#!/usr/bin/env python3
"""Evaluate discovered open-source capabilities before any integration.

No repository is installed or executed. Evaluation is based on registry
metadata and deterministic integration-safety rules.
"""
import json, pathlib
from datetime import datetime, timezone
ROOT=pathlib.Path("data/toolbox")
DISC=ROOT/"discovered-capabilities.json"
REG=ROOT/"capability-registry.json"
OUT=ROOT/"capability-evaluations.json"
PERMISSIVE={"MIT","Apache-2.0","BSD-2-Clause","BSD-3-Clause","MPL-2.0"}
def main():
    d=json.loads(DISC.read_text("utf-8")) if DISC.exists() else {"candidates":[]}
    reg=json.loads(REG.read_text("utf-8")) if REG.exists() else {}
    known={x.get("id") for x in reg.get("candidate_open_source_agent_tools",[])}
    evaluations=[]
    for c in d.get("candidates",[])[:40]:
        lic=c.get("license")
        stars=int(c.get("stars",0) or 0)
        checks={
            "known_license": lic in PERMISSIVE,
            "active_enough": bool(c.get("updated_at")),
            "public_repo": bool(c.get("url")),
            "free_first_compatible": lic in PERMISSIVE
        }
        eligible=all(checks.values()) and stars>=300
        evaluations.append({
            "repository":c.get("id"),"license":lic,"stars":stars,
            "checks":checks,"decision":"EVALUATE_ADAPTER" if eligible else "HOLD",
            "known":c.get("id") in known,
            "next":"build sandbox adapter and benchmark against current worker" if eligible else "collect more metadata"
        })
    out={"schema_version":"1.0","updated_at":datetime.now(timezone.utc).isoformat(),
         "status":"PASS","policy":{"auto_install":False,"auto_execute":False,
         "requires_bounded_adapter":True,"free_first":True},
         "evaluations":evaluations}
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"PASS","evaluated":len(evaluations),
                      "eligible":sum(x["decision"]=="EVALUATE_ADAPTER" for x in evaluations)},ensure_ascii=False))
if __name__=="__main__": main()
