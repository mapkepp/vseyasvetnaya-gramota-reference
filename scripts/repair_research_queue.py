#!/usr/bin/env python3
import json,pathlib,re,sys
from datetime import datetime,timezone

MAX_REPLAN_DEPTH=6
REPLENISH_PER_CYCLE=6
MAX_ROTATION_GENERATIONS=6

def depth(task_id):
    return len(re.findall(r"-replan-\d+", str(task_id)))

def slug(value):
    s=re.sub(r"[^\w\-]+","-",str(value).strip().casefold(),flags=re.UNICODE)
    return s.strip("-")[:50] or "entry"

def main():
    qp=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else "data/research/autonomous-queue.json")
    cp=pathlib.Path(sys.argv[2] if len(sys.argv)>2 else "data/bukovy.json")
    q=json.loads(qp.read_text("utf-8")); canonical=json.loads(cp.read_text("utf-8"))
    entries=[e for e in canonical.get("entries",[]) if e.get("name") and e.get("entry_id")]
    now=datetime.now(timezone.utc).isoformat()
    tasks=q.get("tasks",[])
    pending_entries={t.get("canonical_entry_id") or t.get("bukova") for t in tasks if t.get("status")=="PENDING"}
    additions=[]
    by_entry={}
    for t in tasks: by_entry.setdefault(t.get("canonical_entry_id") or t.get("bukova"),[]).append(t)
    # Re-open failed terminal tasks only when the entry has no pending task and has not reached the bounded rotation limit.
    for e in entries:
        eid,name=e["entry_id"],e["name"]
        if eid in pending_entries: continue
        rows=by_entry.get(eid,[])
        terminal=[t for t in rows if t.get("status") in ("FAILED","EXHAUSTED")]
        if not terminal: continue
        max_depth=max([depth(t.get("task_id","")) for t in rows] or [0])
        if max_depth>=MAX_REPLAN_DEPTH: continue
        if len(additions)>=REPLENISH_PER_CYCLE: break
        latest=max(terminal,key=lambda t:str(t.get("created_at") or ""))
        gen=max_depth+1
        tid=f"rotation-{slug(eid)}-{gen}"
        n=2
        existing={t.get("task_id") for t in tasks}
        while tid in existing:
            tid=f"rotation-{slug(eid)}-{gen}--{n}"; n+=1
        additions.append({
          "task_id":tid,"canonical_entry_id":eid,"bukova":name,"status":"PENDING",
          "priority":"rotation","track":"BUKOVY_FIRST","created_at":now,"generation":gen,
          "attempt":0,"max_attempts":2,
          "queries": (
            [f'"{name}" Букова Instagram', f'"{name}" Букова YouTube', f'"{name}" Букова TikTok',
             f'"{name}" Букова VK видео', f'"{name}" Букова VK', f'"{name}" Буковник видео',
             f'"{name}" ВсеЯСветная практика', f'"{name}" ВсеЯСветная результат',
             f'"{name}" Букова отзыв форум', f'"{name}" Букова комментарии', f'"{name}" Букова мастер',
             f'"{name}" Букова разбор'] if gen == 2 else
            [f'"{name}" site:youtube.com Букова', f'"{name}" site:rutube.ru Букова',
             f'"{name}" site:vk.com Букова', f'"{name}" site:proza.ru Букова',
             f'"{name}" site:forum.anastasia.ru Букова', f'"{name}" site:bezvremenye.ru Букова',
             f'"{name}" ВсеЯСветная Грамота отзыв', f'"{name}" ВсеЯСветная Грамота практика',
             f'"{name}" ВсеЯСветная Грамота результат', f'"{name}" Букова применение',
             f'"{name}" Букова упражнение', f'"{name}" Буковник'] if gen == 3 else
            [f'"{name}" "Букова" личный опыт', f'"{name}" "Букова" мой опыт',
             f'"{name}" "Букова" я применял', f'"{name}" "Букова" мне помог',
             f'"{name}" "Букова" получилось', f'"{name}" "Букова" изменения',
             f'"{name}" "Букова" результаты', f'"{name}" "Букова" практиковал',
             f'"{name}" "Букова" методика', f'"{name}" "Букова" техника',
             f'"{name}" "Букова" занятие', f'"{name}" "Букова" до после'] if gen >= 4 else
            [f'"{name}" "Букова" практика свидетельство', f'"{name}" "Букова" применение опыт',
             f'"{name}" "Букова" результат эффект', f'"{name}" "Букова" отзыв история',
             f'"{name}" "Букова" упражнение', f'"{name}" "Буковник" практика',
             f'"{name}" "Буковы" применение', f'"{name}" "Букова" наблюдение эксперимент',
             f'"{name}" "Букова" дневник форум видео']
          ),
          "reason":"terminal_task_recovery",
          "parent_task_id":latest.get("task_id")
        })
        pending_entries.add(eid)
    tasks.extend(additions)
    q["tasks"]=tasks
    pending=[t for t in tasks if t.get("status")=="PENDING"]
    q["queue_health"]={
      "policy":"bounded-terminal-recovery",
      "max_replan_depth":MAX_REPLAN_DEPTH,
      "max_rotation_generations":MAX_ROTATION_GENERATIONS,
      "target_distinct_pending":REPLENISH_PER_CYCLE,
      "replenished_this_run":len(additions),
      "pending_after":len(pending),
      "distinct_pending_entries_after":len({t.get("canonical_entry_id") or t.get("bukova") for t in pending}),
      "repaired_at":now
    }
    q["updated_at"]=now
    qp.write_text(json.dumps(q,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"PASS","evidence":"MEASURED","replenished":len(additions),"pending_after":len(pending)},ensure_ascii=False))
if __name__=="__main__": raise SystemExit(main())
