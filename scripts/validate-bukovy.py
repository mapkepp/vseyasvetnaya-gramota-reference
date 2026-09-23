#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT / rel).read_text("utf-8"))

data = load("data/bukovy.json")
api = load("api/v1/bukovy.json")
index = load("api/v1/index.json")

entries = data.get("entries", [])
assert data.get("claimed_count") == 147, "claimed_count must remain the published 147 claim"
assert data.get("api_version") == "v1"
assert len(entries) == data["coverage"]["described_entries"]
assert sum(e.get("image_status") == "local-copy" for e in entries) == data["coverage"]["entries_with_local_image"]
assert data["coverage"]["unfilled_claimed_slots"] == data["claimed_count"] - len(entries)

ids = [e.get("entry_id") for e in entries]
assert all(ids), "every entry needs a stable entry_id"
assert len(ids) == len(set(ids)), "entry_id values must be unique"

image_numbers = [e.get("source_image_number") for e in entries if e.get("source_image_number") is not None]
assert len(image_numbers) == len(set(image_numbers)), "source_image_number values must be unique"

for e in entries:
    for key in ("name", "source_url", "claim_status", "entry_id"):
        assert e.get(key), f"missing {key} in entry {e.get('name')!r}"
    if e.get("image_status") == "local-copy":
        image = e.get("image")
        assert image and (ROOT / image).is_file(), f"missing local image for {e['name']}: {image}"

assert api == data, "api/v1/bukovy.json is stale; run scripts/build-api.py"
assert index["endpoints"]["bukovy"] == "/api/v1/bukovy.json"
assert index["endpoints"]["practices"] == "/api/v1/practices.json"
assert index["endpoints"]["index"] == "/api/v1/index.json"
assert index["endpoints"]["schema"] == "/api/v1/bukovy.schema.json"

print(f"PASS: {len(entries)} described entries, {len(image_numbers)} source images indexed, {data['coverage']['unfilled_claimed_slots']} claimed slots still unfilled.")
