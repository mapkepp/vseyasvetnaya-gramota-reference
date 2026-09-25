#!/usr/bin/env python3
"""Архивирует уникальные полезные коммиты веток и безопасно удаляет только явно устаревшие ветки."""
import json, os, subprocess, urllib.request, hashlib
from pathlib import Path
REPO=os.environ.get("GITHUB_REPOSITORY","mapkepp/vseyasvetnaya-gramota-reference")
TOKEN=os.environ["GITHUB_TOKEN"]; API="https://api.github.com"
PRIMARY={"main","dev"}; LEGACY={"development","production","reserve","backup"}
PREFIXES=("automation/","implementation/","research/")
ALLOWED=("scripts/","data/research/","data/toolbox/","api/","research-status.html")
ARCHIVE_WORTHY=ALLOWED+(".github/workflows/","tests/","config/","docs/","README.md","CHANGELOG.md")
ARCH=Path("data/research/branch-archive"); INDEX=ARCH/"index.json"
def sh(*a): return subprocess.run(a,text=True,capture_output=True,check=False)
def api(path,method="DELETE"):
    req=urllib.request.Request(API+path,method=method,headers={"Accept":"application/vnd.github+json","Authorization":f"Bearer {TOKEN}","X-GitHub-Api-Version":"2022-11-28"})
    with urllib.request.urlopen(req,timeout=20) as r: return r.read()
def useful_commit(commit):
    p=sh("git","diff-tree","--no-commit-id","--name-only","-r",commit).stdout.splitlines()
    return [x for x in p if any(x.startswith(a) for a in ARCHIVE_WORTHY)]
def main():
    ARCH.mkdir(parents=True,exist_ok=True)
    idx=json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {"version":1,"commits":{},"patches":{}}
    branches=sh("git","for-each-ref","--format=%(refname:short)","refs/remotes/origin").stdout.splitlines()
    deleted=[]; kept=[]
    for b in branches:
        if b=="origin/HEAD" or not b.startswith("origin/"): continue
        name=b[7:]
        if name in PRIMARY or name not in LEGACY and not name.startswith(PREFIXES): continue
        unique=sh("git","rev-list",f"dev..origin/{name}").stdout.splitlines()
        unarchived_useful=0
        for commit in unique:
            paths=useful_commit(commit)
            if not paths: continue
            if commit in idx["commits"]: continue
            patch=sh("git","show","--binary","--format=email",commit).stdout
            digest=hashlib.sha256(patch.encode()).hexdigest()
            if digest in idx["patches"].values(): idx["commits"][commit]={"sha256":digest,"paths":paths}; continue
            fn=ARCH/(digest+".patch")
            fn.write_text(patch,encoding="utf-8")
            idx["commits"][commit]={"sha256":digest,"paths":paths,"branch":name}
            idx["patches"][str(commit)]=digest
            unarchived_useful+=1
        # Never delete branches needing review; legacy branches may be removed after unique useful commits are archived.
        safe_legacy=name in LEGACY
        safe_trash=name not in PRIMARY and name not in LEGACY and not any(useful_commit(c) for c in unique)
        if safe_legacy or safe_trash and all(not useful_commit(c) or c in idx["commits"] for c in unique):
            try:
                api(f"/repos/{REPO}/git/refs/heads/{name}")
                deleted.append({"branch":name,"reason":"историческая ветка: полезные уникальные коммиты сохранены в архиве"})
            except Exception:
                kept.append({"branch":name,"reason":"удаление не подтверждено"})
        else:
            kept.append({"branch":name,"reason":"не соответствует безопасному правилу удаления"})
    INDEX.write_text(json.dumps(idx,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    Path("data/research/branch-cleanup.json").write_text(json.dumps({"version":1,"deleted":deleted,"kept":kept,"protected":sorted(PRIMARY)},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__": main()
