#!/usr/bin/env python3
import json,sys,pathlib,re
from datetime import datetime,timezone

ACTION_VERBS=re.compile(r"\b(?:нанесла?|наносил[аи]?|ставил[аи]?|поставил[аи]?|применил[аи]?|применял[аи]?|использовал[аи]?|рисовал[аи]?|носил[аи]?|держал[аи]?|прикладывал[аи]?)\b",re.I)
RESULT_MARKERS=re.compile(r"\b(?:результат|сработал[оаи]?|помогл[оаи]?|стал[оаи]?|стало|стала|стали|ощутил[а]?|почувствовал[а]?|увидел[а]?|получил[а]?|заметил[а]?|приснилось|эффект)\b",re.I)
META=re.compile(r"(?:Участник|Сообщения?:|Репутация:|Записан|Печать|Страницы\s+\d|Действия пользователя)",re.I)
BAD_NAMES={"которые","темы","сообщение","сообщения","пользователь","участник","администратор","модератор","форум","записан"}

def valid_candidate(c):
    reasons=[]
    vals={k:str(c.get(k) or "").strip() for k in ("practitioner","bukova","action","reported_result","source_url")}
    for k,v in vals.items():
        if not v: reasons.append("missing:"+k)
    p=vals["practitioner"].casefold()
    if p in BAD_NAMES: reasons.append("generic_or_role_practitioner")
    if "?" in vals["action"]: reasons.append("action_is_question")
    if vals["action"]==vals["reported_result"]: reasons.append("action_equals_result")
    if META.search(vals["action"]) or META.search(vals["reported_result"]): reasons.append("forum_metadata_contamination")
    if not ACTION_VERBS.search(vals["action"]): reasons.append("no_application_verb")
    if not RESULT_MARKERS.search(vals["reported_result"]): reasons.append("no_result_marker")
    excerpts=c.get("source_excerpt_candidates") or []
    common=False
    a=vals["action"][:90]; r=vals["reported_result"][:90]
    for e in excerpts:
        es=str(e)
        if a and a in es and r and r in es: common=True; break
    if not common: reasons.append("action_and_result_not_in_same_excerpt")
    scope=str(c.get("application_scope") or "")
    if scope=="COMPOSITE" and c.get("related_bukovy") and len(c["related_bukovy"])<2:
        reasons.append("composite_scope_missing_components")
    return len(reasons)==0,reasons

def main():
    root=pathlib.Path(sys.argv[1]); ready=[]; rejected=[]; incomplete=[]
    for f in sorted(root.glob("*.normalized.json")):
        d=json.load(open(f,encoding="utf-8"))
        for c in d.get("candidates",[]):
            ok,reasons=valid_candidate(c)
            if ok:
                ready.append(c)
            else:
                rejected.append({"candidate_id":c.get("candidate_id"),"reasons":reasons,"source_url":c.get("source_url"),"bukova":c.get("bukova")})
    payload={"schema_version":"1.1","updated_at":datetime.now(timezone.utc).isoformat(),
             "evidence":"MEASURED","status":"PASS" if ready else "INCOMPLETE",
             "ready_for_human_review":len(ready),"incomplete":len(incomplete),
             "rejected_by_strict_gate":len(rejected),"canonical_mutation":"DISABLED",
             "candidates":[{"candidate_id":c["candidate_id"],"practitioner":c["practitioner"],"bukova":c["bukova"],
             "action":c["action"],"reported_result":c["reported_result"],"source_url":c["source_url"]} for c in ready],
             "rejections":rejected,
             "gate_rules":["identifiable non-generic practitioner","specific Bukova","application verb in action",
             "outcome marker in reported result","action != result","no forum metadata contamination",
             "action and result present in same source excerpt","composite scope preserved"] }
    json.dump(payload,open(root/"practitioner-evidence-gate.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
if __name__=="__main__":main()
