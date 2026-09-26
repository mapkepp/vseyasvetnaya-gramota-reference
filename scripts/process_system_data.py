#!/usr/bin/env python3
"""Track and process newly published system JSON surfaces.

Every discovered/changed JSON receives a durable ledger entry with timestamps,
fingerprint and consumer. This prevents new telemetry from being merely dumped
and forgotten.
"""
import json, pathlib, hashlib
from datetime import datetime, timezone
ROOT=pathlib.Path("."); R=ROOT/"data/research"; OUT=R/"system-data-ledger.json"
now=datetime.now(timezone.utc).isoformat()
try: ledger=json.loads(OUT.read_text(encoding="utf-8"))
except Exception: ledger={"schema_version":"1.0","entries":{}}
entries=ledger.get("entries",{})
for base in (R, ROOT/"data/toolbox"):
    if not base.exists(): continue
    for p in base.rglob("*.json"):
        if p.name in {"system-data-ledger.json","system-experience.json"}: continue
        try:
            raw=p.read_bytes(); obj=json.loads(raw.decode("utf-8"))
        except Exception: continue
        rel=p.as_posix(); fp=hashlib.sha256(raw).hexdigest()[:16]
        e=entries.get(rel,{})
        changed=e.get("fingerprint")!=fp
        if not e: e.update({"first_seen_at":now,"processed_count":0})
        if changed or not e.get("last_processed_at"):
            e["processed_count"]=int(e.get("processed_count",0))+1
            e["last_processed_at"]=now
        e.update({"last_seen_at":now,"fingerprint":fp,"size_bytes":len(raw),
                  "consumer":"status-page + system-self-check + self-improvement",
                  "processing":"registered, timestamped, fingerprinted, available to next improvement cycle"})
        entries[rel]=e
ledger.update({"schema_version":"1.0","updated_at":now,"entries":entries,
               "summary":{"surfaces":len(entries),"processed":sum(int(x.get("processed_count",0)) for x in entries.values())}})
OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(ledger["summary"],ensure_ascii=False))
