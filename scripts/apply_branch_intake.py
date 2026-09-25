#!/usr/bin/env python3
"""Безопасно переносит только прошедшие branch-scan кандидаты в dev."""
import json, subprocess
from pathlib import Path
SCAN=Path("data/research/branch-scan.json")
OUT=Path("data/research/branch-intake.json")
def run(*a,check=True): return subprocess.run(a,text=True,capture_output=True,check=check)
def main():
    d=json.loads(SCAN.read_text(encoding="utf-8")) if SCAN.exists() else {}
    results=[]
    for r in d.get("branches",[]):
        if r.get("class")!="integration-candidate": continue
        b=r["branch"]
        test=run("git","merge","--no-commit","--no-ff",f"origin/{b}",check=False)
        if test.returncode!=0:
            run("git","merge","--abort",check=False)
            results.append({"branch":b,"status":"blocked-conflict"})
            continue
        run("git","merge","--abort",check=False)
        # Candidate is cleanly mergeable; actual merge is deliberately explicit and bounded.
        m=run("git","merge","--no-ff","--no-edit",f"origin/{b}",check=False)
        if m.returncode!=0:
            run("git","merge","--abort",check=False)
            results.append({"branch":b,"status":"blocked-apply-conflict"})
            continue
        results.append({"branch":b,"status":"merged"})
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({"version":1,"language":"ru","base_branch":"dev","results":results},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__": main()
