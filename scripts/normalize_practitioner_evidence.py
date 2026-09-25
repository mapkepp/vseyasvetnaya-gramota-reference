#!/usr/bin/env python3
import json,sys,re,urllib.request
from html.parser import HTMLParser
from datetime import datetime,timezone

ACTION_RE=re.compile(r"([^.!?\n]{0,250}\b(?:нанесла?|наносил[аи]?|ставил[аи]?|поставил[аи]?|применил[аи]?|применял[аи]?|использовал[аи]?|рисовал[аи]?|носил[аи]?|держал[аи]?|прикладывал[аи]?)\b[^.!?\n]{0,700})",re.I)
RESULT_RE=re.compile(r"([^.!?\n]{0,300}\b(?:результат|сработал[оаи]?|помогл[оаи]?|стал[оаи]?|стало|стала|стали|ощутил[а]?|почувствовал[а]?|увидел[а]?|получил[а]?|заметил[а]?|приснилось|эффект)\b[^.!?\n]{0,800})",re.I)
BAD_NAMES={"которые","темы","сообщение","сообщения","пользователь","участник","администратор","модератор","форум","записан"}

class Parser(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]
    def handle_data(self,d):
        d=" ".join(d.split())
        if d:self.parts.append(d)
    def text(self): return " ".join(self.parts)

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"ToolboxEvidenceNormalizer/1.1","Accept-Language":"ru-RU,ru;q=0.9"})
    with urllib.request.urlopen(req,timeout=25) as r:return r.read().decode("utf-8","replace")[:500000]

def windows(text,bukova):
    out=[]; b=re.escape(bukova)
    for m in re.finditer(b,text,re.I):
        out.append(text[max(0,m.start()-1000):min(len(text),m.end()+1500)])
        if len(out)>=40:break
    return out

def infer_practitioner(text):
    pats=[
      r"\b(?:пользователь|практик|мастер|автор|участник)\s+([А-ЯЁA-Z][\wЁё-]{1,30})\b",
      r"\b([А-ЯЁA-Z][\wЁё-]{1,30})\s+(?:пишет|сообщает|рассказывает|использовал[а]?|применял[а]?|наносил[а]?)"
    ]
    for pat in pats:
        for n in re.findall(pat,text,re.I):
            if n.casefold() not in BAD_NAMES:return n
    # Common forum-post signature pattern: username followed by role/metadata.
    for n in re.findall(r"\b([A-Za-zА-ЯЁа-яЁё][\w-]{2,30})\s+(?:Участник|Сообщений|Репутация)",text):
        if n.casefold() not in BAD_NAMES:return n
    return None

def main():
    task=json.load(open(sys.argv[1],encoding="utf-8")); verified=json.load(open(sys.argv[2],encoding="utf-8")); out=sys.argv[3]
    results=[]
    for v in verified.get("verification",[]):
        if not v.get("reachable") or v.get("verification")!="CANDIDATE":continue
        url=v.get("url","")
        try:
            p=Parser();p.feed(fetch(url));text=p.text()
        except Exception:continue
        for w in windows(text,str(task.get("bukova",""))):
            am=ACTION_RE.search(w); rm=RESULT_RE.search(w)
            action=am.group(1).strip() if am else None
            result=rm.group(1).strip() if rm else None
            practitioner=infer_practitioner(w)
            if not practitioner and not action and not result:continue
            composite=bool(re.search(r"\b(?:плюс|вместе|комбинац|став(?:ил[аи]?)\s+.+\s+и\s+.+)\b",w,re.I))
            complete=bool(practitioner and action and result and action!=result and "?" not in action)
            results.append({
              "candidate_id":task["task_id"]+"::"+str(len(results)+1),
              "status":"READY_FOR_REVIEW" if complete else "CANDIDATE",
              "evidence":"MEASURED","practitioner":practitioner,"bukova":task.get("bukova"),
              "action":action,"reported_result":result,"source_url":url,
              "source_title":v.get("title",""),"source_excerpt_candidates":[w[:2500]],
              "context_integrity":"SAME_WINDOW" if (action and result and practitioner) else "INCOMPLETE",
              "application_scope":"COMPOSITE" if composite else "SINGLE_OR_UNDETERMINED",
              "normalization_rule":"Source-reported anecdote only; no efficacy claim; composite staves must not be split.",
              "canonical_mutation":"DISABLED"
            })
            break
    payload={"schema_version":"1.1","generated_at":datetime.now(timezone.utc).isoformat(),"task_id":task["task_id"],
             "bukova":task.get("bukova"),
             "status":"PASS" if any(x["status"]=="READY_FOR_REVIEW" for x in results) else ("CANDIDATE" if results else "INCOMPLETE"),
             "evidence":"MEASURED","candidate_count":len(results),"candidates":results}
    json.dump(payload,open(out,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
if __name__=="__main__":raise SystemExit(main())
