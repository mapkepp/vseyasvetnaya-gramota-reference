#!/usr/bin/env python3
"""Discover candidate open-source agent/tool capabilities without installing them.

The evolution worker records candidates and creates bounded integration proposals.
No arbitrary repository is executed and no dependency is installed automatically.
"""
import json, os, urllib.parse, urllib.request
from datetime import datetime, timezone

ROOT="data/toolbox"
REG=os.path.join(ROOT,"capability-registry.json")
OUT=os.path.join(ROOT,"discovered-capabilities.json")

QUERIES=[
    "topic:agent-framework language:Python stars:>500",
    "topic:multi-agent language:Python stars:>500",
    "topic:tool-calling language:Python stars:>300",
    "topic:mcp-server language:Python stars:>300",
    "topic:local-llm language:Python stars:>300"
]

def gh(q):
    url="https://api.github.com/search/repositories?"+urllib.parse.urlencode({"q":q,"sort":"updated","order":"desc","per_page":8})
    req=urllib.request.Request(url,headers={"Accept":"application/vnd.github+json","Authorization":"Bearer "+os.environ.get("GITHUB_TOKEN","")})
    with urllib.request.urlopen(req,timeout=20) as r:return json.loads(r.read().decode())

def main():
    os.makedirs(ROOT,exist_ok=True)
    candidates=[]
    for q in QUERIES:
        try:
            for x in gh(q).get("items",[]):
                candidates.append({
                    "id":x.get("full_name"),"url":x.get("html_url"),"stars":x.get("stargazers_count",0),
                    "license":(x.get("license") or {}).get("spdx_id"),
                    "updated_at":x.get("updated_at"),"description":x.get("description")
                })
        except Exception as e:
            candidates.append({"query":q,"status":"ERROR","error":type(e).__name__})
    uniq={x.get("id"):x for x in candidates if x.get("id")}
    registry=json.load(open(REG,encoding="utf-8")) if os.path.exists(REG) else {}
    known={x.get("id") for x in registry.get("candidate_open_source_agent_tools",[])}
    proposals=[]
    for x in sorted(uniq.values(),key=lambda z:(z.get("stars",0),z.get("updated_at","")),reverse=True):
        if x["id"] not in known and x.get("license") in {"MIT","Apache-2.0","BSD-2-Clause","BSD-3-Clause","MPL-2.0"}:
            proposals.append({"repository":x["id"],"action":"EVALUATE","reason":"new permissively-licensed candidate",
                              "next":"inspect docs/license/security; integrate only through bounded adapter"})
    out={"schema_version":"1.0","updated_at":datetime.now(timezone.utc).isoformat(),
         "status":"PASS","candidates":list(uniq.values())[:40],"integration_proposals":proposals[:12]}
    json.dump(out,open(OUT,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
    print(json.dumps({"candidates":len(uniq),"proposals":len(proposals)},ensure_ascii=False))

if __name__=="__main__":main()
