#!/usr/bin/env python3
"""Record durable operational experience from every autonomous research cycle."""
import json, pathlib, hashlib
from datetime import datetime, timezone

ROOT=pathlib.Path(".")
R=ROOT/"data/research"
EXP=R/"system-experience.json"
HEALTH=R/"system-health.json"
HIST=R/"research-history.json"
METRICS=R/"cycle-metrics.json"

def load(p,d):
    try:return json.loads(p.read_text(encoding="utf-8"))
    except Exception:return d

now=datetime.now(timezone.utc).isoformat()
history=load(HIST,{"cycles":[]})
metrics=load(METRICS,{})
health=load(HEALTH,{"status":"NOT_YET_CHECKED","issues":[],"repairs":[]})
cycles=history.get("cycles",[])
latest=cycles[0] if cycles else {}
if not latest.get("cycle_id"):
    print(json.dumps({"status":"PASS","type":"health_only","message":"Нет завершённого research-cycle; опыт цикла не записывается."},ensure_ascii=False))
    raise SystemExit(0)
tasks=latest.get("tasks",[])
findings=sum(int(t.get("findings_count") or 0) for t in tasks)
sources=sum(int(t.get("source_count") or 0) for t in tasks)
verified=sum(1 for t in tasks if t.get("verified"))
normalized=sum(1 for t in tasks if t.get("normalized"))
failed=sum(1 for t in tasks if str(t.get("status","")).upper() in {"FAILED","FAIL","ERROR"})
duration=latest.get("duration_seconds")

lessons=[]
if failed: lessons.append(f"Цикл содержит {failed} неуспешных задач — ошибки нужно учитывать при следующем запуске.")
if sources==0 and tasks: lessons.append("Цикл не получил источников; при следующем запуске повышать контроль качества поиска.")
if verified<findings and findings: lessons.append("Не все найденные свидетельства прошли проверку; не считать необработанные находки доказанными.")
if normalized<verified and verified: lessons.append("Часть проверенных материалов не нормализована; практическое применение не переносить в канон автоматически.")
if duration is not None and tasks:
    lessons.append(f"Фактическая длительность последнего цикла: {duration:.1f} с; использовать как базу для контроля зависаний.")
if not lessons: lessons.append("Цикл завершён без зарегистрированных аномалий; сохраняем успешную схему как рабочий опыт.")

fingerprint=hashlib.sha256(json.dumps({
    "cycle_id":latest.get("cycle_id"),"findings":findings,"sources":sources,
    "verified":verified,"normalized":normalized,"failed":failed,"health":health.get("status")
},sort_keys=True).encode()).hexdigest()[:16]

exp=load(EXP,{"schema_version":"2.0","events":[],"learning_policy":{}})
events=[e for e in exp.get("events",[]) if e.get("type")!="research_cycle" or e.get("cycle_id")]
event={
    "at":now,"type":"research_cycle","cycle_id":latest.get("cycle_id"),
    "status":health.get("status","UNKNOWN"),"fingerprint":fingerprint,
    "measured":{"tasks":len(tasks),"findings":findings,"sources":sources,"verified":verified,
                "normalized":normalized,"failed":failed,"duration_seconds":duration},
    "lessons":lessons,
    "next_cycle_hints":[
        "учитывать фактические ошибки и длительности предыдущих циклов",
        "не переносить непроверенные практические свидетельства в канон",
        "повторно использовать только подтверждённые поисковые стратегии"
    ]
}
if not any(e.get("fingerprint")==fingerprint for e in events):
    events.append(event)
exp.update({
    "schema_version":"2.0","updated_at":now,"events":events[-500:],
    "learning_policy":{
        "enabled":True,"learn_from_cycles":True,"learn_from_failures":True,
        "use_in_next_cycle":True,"deduplicate":True,"retain_last":500,
        "canonical_mutation_from_experience":"DISABLED"
    },
    "last_cycle_id":latest.get("cycle_id"),
    "last_lessons":lessons
})
EXP.parent.mkdir(parents=True,exist_ok=True)
EXP.write_text(json.dumps(exp,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"status":"PASS","cycle_id":latest.get("cycle_id"),"lessons":lessons},ensure_ascii=False))
