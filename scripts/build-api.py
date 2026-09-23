#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
api = ROOT / "api" / "v1"
api.mkdir(parents=True, exist_ok=True)

bukovy = json.loads((ROOT / "data" / "bukovy.json").read_text("utf-8"))
practices = json.loads((ROOT / "data" / "practices.json").read_text("utf-8"))

index = {
    "api_version": "v1",
    "service": "bukovy-reference",
    "description": "Static JSON API for the research reference catalog.",
    "endpoints": {
        "bukovy": "/api/v1/bukovy.json",
        "practices": "/api/v1/practices.json",
        "index": "/api/v1/index.json",
        "schema": "/api/v1/bukovy.schema.json"
    },
    "source_policy": "Catalog claims are attributed to their sources; missing claimed entries are not invented."
}

(api / "bukovy.json").write_text(json.dumps(bukovy, ensure_ascii=False, indent=2) + "\n", "utf-8")
(api / "practices.json").write_text(json.dumps(practices, ensure_ascii=False, indent=2) + "\n", "utf-8")
(api / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", "utf-8")
print(f"API generated: {len(bukovy.get('entries', []))} catalog entries")
