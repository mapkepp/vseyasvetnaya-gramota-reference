#!/usr/bin/env python3
import json, pathlib, datetime

ROOT = pathlib.Path(".")
OUT = ROOT / "data/research/status-surface-registry.json"
EXCLUDE = {"status-surface-registry.json"}
LABELS = {
    "autonomous-status.json":"Состояние координатора",
    "autonomous-queue.json":"Очередь исследований",
    "worker-status.json":"Состояние исследовательского worker",
    "active-tasks.json":"Активные задачи",
    "cycle-task-manifest.json":"Манифест текущего цикла",
    "cycle-metrics.json":"Метрики исследовательского цикла",
    "agent-manifest.json":"Манифест специализированных агентов",
    "self-improvement.json":"Предложения самоулучшения",
    "self-improvement-application.json":"Результат применения самоулучшения",
    "discovered-capabilities.json":"Найденные возможности тулбокса",
    "capability-evaluations.json":"Оценка возможностей тулбокса",
}
def label(p):
    n=pathlib.Path(p).name
    if n in LABELS: return LABELS[n]
    stem=pathlib.Path(p).stem.replace("-"," ").replace("_"," ")
    return "Данные системы: "+stem
def desc(p):
    n=pathlib.Path(p).name
    if n in LABELS: return "Автоматически публикуемые данные состояния и работы системы."
    return "Новый автоматически обнаруженный JSON-источник; тулбокс добавил его в статусную страницу."
def main():
    found=[]
    for root in ("data/research","data/toolbox"):
        for p in sorted((ROOT/root).rglob("*.json")):
            rel=p.as_posix()
            if p.name in EXCLUDE or "/worker-results/" in rel and not any(k in p.name for k in (".result.json",".verified.json",".normalized.json",".specialists.json")):
                continue
            found.append(rel)
    old={}
    if OUT.exists():
        try: old={x.get("path"):x for x in json.loads(OUT.read_text(encoding="utf-8")).get("surfaces",[])}
        except Exception: old={}
    surfaces=[]
    for p in found:
        item=old.get(p,{})
        item.update({"path":p,"label":item.get("label") or label(p),"description":item.get("description") or desc(p),"status":"READY"})
        try: item["updated_at"]=datetime.datetime.fromtimestamp((ROOT/p).stat().st_mtime,datetime.timezone.utc).isoformat().replace("+00:00","Z")
        except OSError: pass
        surfaces.append(item)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({"version":1,"generated_by":"status-surface-sync","surfaces":surfaces},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__": main()
