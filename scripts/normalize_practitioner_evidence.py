#!/usr/bin/env python3
import json,sys,re,urllib.request
from html.parser import HTMLParser
from datetime import datetime,timezone
from urllib.parse import urlparse

REQUIRED=["practitioner","bukova","action","reported_result","source_url"]

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]
    def handle_data(self,d):
        d=" ".join(d.split())
        if d:self.parts.append(d)
    def text(self): return " ".join(self.parts)

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"ToolboxEvidenceNormalizer/1.0"})
    with urllib.request.urlopen(req,timeout=25) as r:
        return r.read().decode("utf-8","replace")[:300000]

def sentence_candidates(text, bukova):
    b=re.escape(str(bukova))
    rx=re.compile(r"[^.!?\n]{0,500}\b"+b+r"\b[^.!?\n]{0,800}[.!?]",re.I)
    return [x.strip() for x in rx.findall(text)][:30]

def infer_practitioner(text, context):
    names=[]
    for pat in [
        r"\b(?:пользователь|практик|мастер|автор|участник)\s+([А-ЯЁA-Z][\wЁё-]{1,30})",
        r"\b([А-ЯЁA-Z][\wЁё-]{1,30})\s+(?:пишет|сообщает|рассказывает|использовал|применял|наносил)"
    ]:
        names += re.findall(pat,text,re.I)
    if context.get("practitioner"): names.append(str(context["practitioner"]))
    cleaned=[]
    for n in names:
        if n.lower() not in {"букова","сначала","после","тогда","обычно"} and n not in cleaned: cleaned.append(n)
    return cleaned[0] if cleaned else None

def infer_action(snips):
    verbs=r"(?:наносил|нанес|применял|применил|использовал|использует|ставил|поставил|рисовал|носил|держал|прикладывал|прикладывал)"
    for s in snips:
        m=re.search(r"([^.!?]{0,250}"+verbs+r"[^.!?]{0,500})",s,re.I)
        if m:return m.group(1).strip()
    return None

def infer_result(snips):
    verbs=r"(?:получил|получила|получили|заметил|заметила|стало|стала|стали|помогло|сработало|приснилось|видел|увидел|ощутил|почувствовал|сообщает)"
    for s in snips:
        m=re.search(r"([^.!?]{0,300}"+verbs+r"[^.!?]{0,700})",s,re.I)
        if m:return m.group(1).strip()
    return None

def main():
    task=json.load(open(sys.argv[1],encoding="utf-8"))
    verified=json.load(open(sys.argv[2],encoding="utf-8"))
    out=sys.argv[3]
    candidates=[]
    for v in verified.get("verification",[]):
        if not v.get("reachable") or v.get("verification")!="CANDIDATE": continue
        url=v.get("url","")
        try:
            raw=fetch(url); parser=TextParser(); parser.feed(raw); txt=parser.text()
        except Exception:
            continue
        snippets=sentence_candidates(txt,str(task.get("bukova","")))
        practitioner=infer_practitioner(txt,task)
        action=infer_action(snippets)
        result=infer_result(snippets)
        complete=bool(practitioner and task.get("bukova") and action and result and url)
        candidates.append({
            "candidate_id":task["task_id"]+"::"+str(len(candidates)+1),
            "status":"READY_FOR_REVIEW" if complete else "INCOMPLETE",
            "evidence":"MEASURED",
            "practitioner":practitioner,
            "bukova":task.get("bukova"),
            "action":action,
            "reported_result":result,
            "source_url":url,
            "source_title":v.get("title",""),
            "source_excerpt_candidates":snippets[:5],
            "normalization_rule":"Source-reported anecdote only; no efficacy claim; composite staves must not be split.",
            "canonical_mutation":"DISABLED"
        })
    payload={"schema_version":"1.0","generated_at":datetime.now(timezone.utc).isoformat(),
             "task_id":task["task_id"],"bukova":task.get("bukova"),
             "status":"PASS" if any(x["status"]=="READY_FOR_REVIEW" for x in candidates) else "INCOMPLETE",
             "evidence":"MEASURED","candidate_count":len(candidates),"candidates":candidates}
    json.dump(payload,open(out,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
    return 0
if __name__=="__main__": raise SystemExit(main())
