#!/usr/bin/env python3
"""Сканирование веток и подготовка безопасного автоматического переноса полезных изменений."""
import json, os, subprocess, urllib.request, urllib.parse
from pathlib import Path

REPO=os.environ.get("GITHUB_REPOSITORY","mapkepp/vseyasvetnaya-gramota-reference")
TOKEN=os.environ.get("GITHUB_TOKEN","")
API="https://api.github.com"
OUT=Path("data/research/branch-scan.json")
ARCHIVE=Path("data/research/branch-archive.json")
PRIMARY={"main","dev"}
LEGACY={"development","production","reserve","backup"}
PREFIXES=("automation/","implementation/","research/")
ALLOWED_PREFIXES=("scripts/","data/research/","data/toolbox/","api/","research-status.html")
ARCHIVE_WORTHY_PREFIXES=ALLOWED_PREFIXES+(".github/workflows/","tests/","config/","docs/","README.md","CHANGELOG.md")
BLOCKED_PATHS=("secrets","credentials",".env")
def api(path):
    req=urllib.request.Request(API+path,headers={"Accept":"application/vnd.github+json","Authorization":f"Bearer {TOKEN}","X-GitHub-Api-Version":"2022-11-28"})
    with urllib.request.urlopen(req,timeout=20) as r: return json.load(r)
def cmp(base,head):
    return api(f"/repos/{REPO}/compare/{urllib.parse.quote(base,safe='')}...{urllib.parse.quote(head,safe='')}")
def classify(name, ahead, behind, files):
    if name in PRIMARY: return "protected"
    if name in LEGACY: return "legacy"
    if not name.startswith(PREFIXES): return "unclassified"
    if ahead==0: return "obsolete"
    if not files: return "obsolete"
    allowed_files=[f for f in files if any(f.startswith(p) for p in ALLOWED_PREFIXES) and not any(x in f.lower() for x in BLOCKED_PATHS)]
    archive_worthy=[f for f in files if any(f.startswith(p) for p in ARCHIVE_WORTHY_PREFIXES) and not any(x in f.lower() for x in BLOCKED_PATHS)]
    blocked_files=[f for f in files if f not in allowed_files]
    if not archive_worthy and ahead<=20:
        return "trash-candidate"
    if allowed_files and not blocked_files and ahead<=20:
        return "integration-candidate"
    if allowed_files and len(allowed_files)<=10 and ahead<=20:
        return "partial-integration-candidate"
    return "review-required"
def main():
    branches=api(f"/repos/{REPO}/branches?per_page=100") 
    rows=[]
    archive_items=[]
    for b in branches:
        name=b["name"]
        try:
            c=cmp("dev",name)
            files=[x["filename"] for x in c.get("files",[])]
            row={"branch":name,"class":classify(name,c.get("ahead_by",0),c.get("behind_by",0),files),
                 "ahead_of_dev":c.get("ahead_by",0),"behind_dev":c.get("behind_by",0),
                 "commits":c.get("total_commits",0),"files":files[:100],"allowed_files":[f for f in files if any(f.startswith(p) for p in ALLOWED_PREFIXES) and not any(x in f.lower() for x in BLOCKED_PATHS)],
                 "archive_worthy_files":archive_worthy,
                 "merge_base":(c.get("merge_base_commit") or {}).get("sha"),
                 "status":c.get("status")}
        except Exception as e:
            row={"branch":name,"class":"scan-error","error":str(e)}
        if row["class"] in ("legacy","obsolete") and row.get("branch") not in PRIMARY:
            archive_items.append({"branch":name,"ahead_of_dev":row.get("ahead_of_dev"),"commits":row.get("commits"),"files":row.get("files",[])})
        rows.append(row)
    rows.sort(key=lambda x:(x["class"],x["branch"]))
    candidates=[r for r in rows if r["class"] in ("integration-candidate","partial-integration-candidate")]
    OUT.parent.mkdir(parents=True,exist_ok=True)
    existing=json.loads(ARCHIVE.read_text(encoding="utf-8")) if ARCHIVE.exists() else {"version":1,"items":{}}
    for item in archive_items:
        key=item["branch"]+":"+str(item.get("commits"))+":"+str(item.get("files",[]))
        existing["items"][key]=item
    ARCHIVE.write_text(json.dumps({"version":1,"language":"ru","purpose":"уникальный резерв полезных изменений до удаления веток","dedup_key":"branch+commit_count+file_list","items":existing["items"]},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    OUT.write_text(json.dumps({"version":2,"language":"ru","base_branch":"dev","protected":sorted(PRIMARY),
      "policy":{"auto_apply":"integration-candidate или partial-integration-candidate; максимум 20 коммитов; только разрешённые пути; частичные ветки переносятся только как отдельный diff",
                "never_auto_apply":["main","dev","legacy","review-required","scan-error"],
      "archive_worthy_paths":list(ARCHIVE_WORTHY_PREFIXES),
                "next_step":"apply_branch_intake.py"},
      "summary":{"branches":len(rows),"integration_candidates":len(candidates),"review_required":sum(r["class"]=="review-required" for r in rows),
                 "obsolete":sum(r["class"] in ("obsolete","trash-candidate") for r in rows)},
      "branches":rows},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__": main()
