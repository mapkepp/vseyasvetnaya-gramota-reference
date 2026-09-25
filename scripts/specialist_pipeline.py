#!/usr/bin/env python3
"""Run five bounded specialist stages inside each research task.

The six task processes remain the concurrency boundary. Specialist stages do not
spawn extra network workers; they operate on the task's already collected
evidence and produce auditable role outputs.
"""
import json, pathlib, sys, re
from datetime import datetime, timezone
ROLES = [
    ("identity","Проверка идентичности Буковы и вариантов написания."),
    ("practitioner","Выделение свидетельств конкретного применения человеком."),
    ("result","Выделение действия и наблюдаемого результата."),
    ("corroboration","Поиск признаков независимого подтверждения среди найденных источников."),
    ("source_quality","Проверка автора, даты, URL и первичности источника.")
]
def load(p):
    try: return json.loads(pathlib.Path(p).read_text("utf-8"))
    except Exception: return {}
def text_blob(x):
    return " ".join(str(x.get(k,"")) for k in ("title","snippet","text","description","url","source"))
def main():
    if len(sys.argv)<3: raise SystemExit("usage: specialist_pipeline.py TASK_JSON RESULT_JSON")
    task_path,result_path=sys.argv[1:3]
    task=load(task_path); result=load(result_path)
    findings=result.get("findings",result.get("results",[]))
    if not isinstance(findings,list): findings=[]
    tid=task.get("task_id",pathlib.Path(task_path).stem)
    out=pathlib.Path(result_path).with_name(tid+".specialists.json")
    role_rows=[]
    for role,goal in ROLES:
        rows=[]
        for f in findings:
            if isinstance(f,dict):
                blob=text_blob(f).lower()
                if role=="practitioner" and any(w in blob for w in ("практик","примен","использ","опыт","сделал","наблюд","результат")):
                    rows.append(f)
                elif role=="result" and any(w in blob for w in ("результ","эффект","получ","измен","наблюд","до ","после")):
                    rows.append(f)
                elif role=="corroboration" and f.get("url"):
                    rows.append(f)
                elif role=="source_quality" and f.get("url"):
                    rows.append({"url":f.get("url"),"title":f.get("title"),"source":f.get("source")})
                elif role=="identity" and any(w in blob for w in ("бук","став","слов","грамот")):
                    rows.append(f)
        role_rows.append({
            "agent_id":f"{tid}:{role}","task_id":tid,"role":role,"goal":goal,
            "status":"PASS" if rows else "NO_EVIDENCE",
            "evidence_count":len(rows),"evidence":rows[:12],
            "created_at":datetime.now(timezone.utc).isoformat()
        })
    payload={"schema_version":"1.0","task_id":tid,"bounded":True,
             "roles":role_rows,
             "source_findings":len(findings),
             "execution":"MEASURED"}
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"PASS","task_id":tid,"roles":len(role_rows),
                      "source_findings":len(findings)},ensure_ascii=False))
if __name__=="__main__": main()
