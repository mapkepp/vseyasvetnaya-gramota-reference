#!/usr/bin/env python3
"""Autonomous Bukovy research worker.

Reads one task JSON and writes a structured result JSON.
Requires TAVILY_API_KEY in the environment.
No canonical data is modified by this worker: it only produces research evidence.
"""
import json, os, sys, urllib.request, urllib.error
from datetime import datetime, timezone

def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: research_worker.py TASK_FILE OUTPUT_FILE")
    task_file, output_file = sys.argv[1:]
    task = json.load(open(task_file, encoding="utf-8"))
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        result = {"schema_version":"1.0","task_id":task["task_id"],
                  "status":"BLOCKED","evidence":"MEASURED",
                  "detail":"TAVILY_API_KEY is not configured."}
        json.dump(result, open(output_file,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
        return 2

    payload = {
        "api_key": key,
        "query": task["query"],
        "search_depth": "advanced",
        "max_results": 8,
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False
    }
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type":"application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data=json.load(resp)
    except Exception as exc:
        result={"schema_version":"1.0","task_id":task["task_id"],
                "status":"FAIL","evidence":"MEASURED","detail":str(exc)}
        json.dump(result,open(output_file,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
        return 1

    findings=[]
    for item in data.get("results",[]):
        title=item.get("title") or ""
        url=item.get("url") or ""
        content=item.get("content") or ""
        if not url or not content:
            continue
        findings.append({
            "claim": content[:4000],
            "sources":[{"url":url,"title":title}],
            "evidence_type":"web_search_result",
            "confidence":"UNSPECIFIED",
            "conflicts":[]
        })
    result={
        "schema_version":"1.0","task_id":task["task_id"],"status":"PASS",
        "evidence":"MEASURED","generated_at":datetime.now(timezone.utc).isoformat(),
        "query":task["query"],"findings":findings
    }
    json.dump(result,open(output_file,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
