#!/usr/bin/env python3
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(r): return json.loads((ROOT/r).read_text("utf-8"))
data=load("data/bukovy.json"); api=load("api/v1/bukovy.json"); profiles=load("api/v1/bukovy-profiles.json"); histories=load("data/practice/practitioner-histories.json"); api_histories=load("api/v1/practitioner-histories.json"); index=load("api/v1/index.json")
entries=data.get("entries",[]); assert data.get("claimed_count")==147 and data.get("api_version")=="v1"; assert len(entries)==data["coverage"]["described_entries"]; assert sum(e.get("image_status")=="local-copy" for e in entries)==data["coverage"]["entries_with_local_image"]; assert data["coverage"]["unfilled_claimed_slots"]==data["claimed_count"]-len(entries)
ids=[e.get("entry_id") for e in entries]; assert all(ids) and len(ids)==len(set(ids)); nums=[e.get("source_image_number") for e in entries if e.get("source_image_number") is not None]; assert len(nums)==len(set(nums))
for e in entries:
 for k in ("name","source_url","claim_status","entry_id"): assert e.get(k),f"missing {k}"
 if e.get("image_status")=="local-copy": assert e.get("image") and (ROOT/e["image"]).is_file()
assert api==data and api_histories==histories
for k,v in {"bukovy":"/api/v1/bukovy.json","bukovy_profiles":"/api/v1/bukovy-profiles.json","bukovy_profile_template":"/api/v1/bukovy/{entry_id}.json","practices":"/api/v1/practices.json","practitioner_histories":"/api/v1/practitioner-histories.json","index":"/api/v1/index.json","schema":"/api/v1/bukovy.schema.json","bukovy_profile_schema":"/api/v1/bukovy-profile.schema.json","profile_manifest":"/api/v1/bukovy-manifest.json","bukovy_summary":"/api/v1/bukovy-summary.json"}.items(): assert index["endpoints"][k]==v
assert profiles["profile_count"]==len(entries)
summary=load("api/v1/bukovy-summary.json")
assert summary["profile_count"]==len(entries) and [x["entry_id"] for x in summary["entries"]]==ids
manifest=load("api/v1/bukovy-manifest.json")
assert manifest["profile_count"]==len(entries) and manifest["entries"]==ids and manifest["summary"]=="/api/v1/bukovy-summary.json" and [p["entry_id"] for p in profiles["entries"]]==ids
required={"identity","glyph","source","claimed_description","practical_applications","practitioner_stories","evidence_and_limits","recovery"}
for e in entries:
 assert len(e.get("description_claim","")) <= 1000, f"description unexpectedly long: {e.get('entry_id')}"
for i,p in enumerate(profiles["entries"]):
 assert required<=set(p["blocks"]) and (ROOT/"api/v1/bukovy"/f"{p['entry_id']}.json").is_file()
 s=summary["entries"][i]
 assert p["entry_id"]==s["entry_id"] and p.get("name")==s["name"]
 assert len(p["blocks"].get("practical_applications",[]))==s["counts"]["practical_applications"]
 assert len(p["blocks"].get("practitioner_stories",[]))==s["counts"]["practitioner_stories"]
 assert p["blocks"]["claimed_description"]["text"]==s["claimed_description"]["text"] and p["blocks"]["claimed_description"].get("display_text")
 assert len(p["blocks"]["claimed_description"]["display_text"])<=1000
 individual=load(Path("api/v1/bukovy")/f"{p['entry_id']}.json")
 assert individual==p
story_ids=[s.get("story_id") for s in histories.get("stories",[])]; assert all(story_ids) and len(story_ids)==len(set(story_ids))
for s in histories.get("stories",[]): assert s.get("action") and s.get("reported_result") and s.get("source_urls")
print(f"PASS: {len(entries)} canonical Bukovy, {len(profiles['entries'])} per-Bukova profiles, {len(story_ids)} practitioner histories; {data['coverage']['unfilled_claimed_slots']} claimed slots still unfilled.")
