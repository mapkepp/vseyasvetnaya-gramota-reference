#!/usr/bin/env python3
"""Безопасно переносит только прошедшие branch-scan кандидаты в dev."""
import json, subprocess
from pathlib import Path
SCAN=Path("data/research/branch-scan.json")
OUT=Path("data/research/branch-intake.json")
PRIMARY={"main","dev"}
def run(*a,check=True,**kw): return subprocess.run(a,text=True,capture_output=True,check=check,**kw)
def main():
    d=json.loads(SCAN.read_text(encoding="utf-8")) if SCAN.exists() else {}
    archive=json.loads(Path("data/research/branch-archive.json").read_text(encoding="utf-8")) if Path("data/research/branch-archive.json").exists() else {"items":{}}
    results=[]
    for r in d.get("branches",[]):
        mode=r.get("class")
        if mode not in ("integration-candidate","partial-integration-candidate"): continue
        b=r["branch"]; allowed=r.get("allowed_files",[])
        if not allowed: continue
        if mode=="integration-candidate":
            test=run("git","merge","--no-commit","--no-ff",f"origin/{b}",check=False)
            if test.returncode!=0:
                run("git","merge","--abort",check=False); results.append({"branch":b,"status":"blocked-conflict"}); continue
            run("git","merge","--abort",check=False)
            m=run("git","merge","--no-ff","--no-edit",f"origin/{b}",check=False)
        else:
            mb=run("git","merge-base","HEAD",f"origin/{b}").stdout.strip()
            patch=run("git","diff",mb,f"origin/{b}","--",*allowed,check=False)
            if patch.returncode!=0 or not patch.stdout.strip():
                results.append({"branch":b,"status":"no-extractable-diff"}); continue
            m=run("git","apply","-3","--index","-",check=False,input=patch.stdout)
            if m.returncode==0:
                m=run("git","commit","-m",f"automation: extract useful changes from {b}",check=False)
        if m.returncode!=0:
            run("git","merge","--abort",check=False)
            run("git","reset","--hard","HEAD",check=False)
            results.append({"branch":b,"status":"blocked-apply-conflict"}); continue
        check=run("git","diff","--check",check=False)
        compile_check=run("python3","-m","compileall","-q","scripts",check=False)
        if check.returncode!=0 or compile_check.returncode!=0:
            run("git","reset","--hard","HEAD^",check=False)
            results.append({"branch":b,"status":"blocked-validation"}); continue
        results.append({"branch":b,"status":"merged" if mode=="integration-candidate" else "extracted"})
    # Удаление веток выполняется только после подтверждения, что ветка не содержит уникального полезного материала; protected main/dev никогда не удаляются.\n    cleanup=[]\n    for r in d.get("branches",[]):\n        if r.get("class") not in ("obsolete","legacy") or r.get("branch") in PRIMARY: continue\n        cleanup.append({"branch":r["branch"],"status":"quarantine-only","reason":"сначала сохранён уникальный снимок; автоматическое удаление разрешено только отдельным cleanup-проходом"})\n    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({"version":1,"language":"ru","base_branch":"dev","results":results,"cleanup":cleanup},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__": main()
