#!/usr/bin/env python3
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(r): return json.loads((ROOT/r).read_text("utf-8"))
data=load("data/bukovy.json"); api=load("api/v1/bukovy.json"); profiles=load("api/v1/bukovy-profiles.json"); histories=load("data/practice/practitioner-histories.json"); api_histories=load("api/v1/practitioner-histories.json"); index=load("api/v1/index.json"); recovery_pages=load("data/recovery/historical-six-pages.json"); recovery_evidence=load("data/recovery/secondary-evidence.json"); recovery_candidates=load("data/recovery/147-candidates.json"); recovery_api=load("api/v1/recovery.json")
entries=data.get("entries",[]); assert data.get("claimed_count")==147 and data.get("api_version")=="v1"; assert len(entries)==data["coverage"]["described_entries"]; assert sum(e.get("image_status")=="local-copy" for e in entries)==data["coverage"]["entries_with_local_image"]; assert data["coverage"]["unfilled_claimed_slots"]==data["claimed_count"]-len(entries)
ids=[e.get("entry_id") for e in entries]; assert all(ids) and len(ids)==len(set(ids)); nums=[e.get("source_image_number") for e in entries if e.get("source_image_number") is not None]; assert len(nums)==len(set(nums))
for e in entries:
 for k in ("name","source_url","claim_status","entry_id"): assert e.get(k),f"missing {k}"
 if e.get("image_status")=="local-copy": assert e.get("image") and (ROOT/e["image"]).is_file()
assert api==data and api_histories==histories
assert recovery_pages["status"]=="research-only" and recovery_pages["canonical_inclusion"] is False
assert recovery_evidence["status"]=="research-only" and recovery_evidence["purpose"].startswith("Evidence records")
assert recovery_candidates["status"]=="research-only" and recovery_candidates["canonical_inclusion"] is False
assert len({r["evidence_id"] for r in recovery_evidence["records"]})==len(recovery_evidence["records"])
assert all((r.get("canonical_entry_id") is None or r.get("canonical_entry_id") in ids) for r in recovery_evidence["records"])
assert len({c["name"] for c in recovery_candidates["candidates"]})==len(recovery_candidates["candidates"])
canonical_names={e.get("name") for e in entries}
assert all(c.get("status")=="candidate" and c.get("name") not in canonical_names for c in recovery_candidates["candidates"])
expected_pages=[
 ("Та-Ё","http://gramota.org/alfavit01.html"),
 ("Ёк-Ио","http://gramota.org/alfavit02.html"),
 ("Йо-Пи","http://gramota.org/alfavit03.html"),
 ("Па-Ер","http://gramota.org/alfavit04.html"),
 ("Еры-Исто","http://gramota.org/alfavit05.html"),
 ("Ису-Ятый","http://gramota.org/alfavit06.html"),
]
assert [(p["label"],p["historical_url"]) for p in recovery_pages["pages"]]==expected_pages
assert all(p.get("status")=="direct-unavailable" for p in recovery_pages["pages"])
assert index["endpoints"]["recovery"]=="/api/v1/recovery.json" and index["endpoints"]["recovery_schema"]=="/api/v1/recovery.schema.json"
assert recovery_api["api_version"]=="v1" and recovery_api["recovery_version"]=="v1" and recovery_api["status"]=="research-only"
assert recovery_api["canonical_count"]==data["claimed_count"] and recovery_api["canonical_described_count"]==len(entries) and recovery_api["canonical_unfilled_count"]==data["coverage"]["unfilled_claimed_slots"]
assert recovery_api["candidate_count"]==len(recovery_candidates["candidates"]) and recovery_api["secondary_evidence_count"]==len(recovery_evidence["records"])
assert recovery_api["candidate_count"]!=recovery_api["canonical_unfilled_count"]
assert recovery_api["historical_visual_pages"]==recovery_pages["pages"]
assert recovery_api["rules"]["canonical_inclusion"] is False
for k,v in {"bukovy":"/api/v1/bukovy.json","bukovy_profiles":"/api/v1/bukovy-profiles.json","bukovy_profile_template":"/api/v1/bukovy/{entry_id}.json","practices":"/api/v1/practices.json","practitioner_histories":"/api/v1/practitioner-histories.json","index":"/api/v1/index.json","schema":"/api/v1/bukovy.schema.json","bukovy_profile_schema":"/api/v1/bukovy-profile.schema.json","profile_manifest":"/api/v1/bukovy-manifest.json","bukovy_summary":"/api/v1/bukovy-summary.json"}.items(): assert index["endpoints"][k]==v
assert profiles["profile_count"]==len(entries)
summary=load("api/v1/bukovy-summary.json")
assert summary["api_version"]=="v1" and summary["summary_version"]=="v1"
assert summary["profile_count"]==len(entries) and [x["entry_id"] for x in summary["entries"]]==ids
manifest=load("api/v1/bukovy-manifest.json")
assert manifest["profile_count"]==len(entries) and manifest["entries"]==ids and manifest["summary"]=="/api/v1/bukovy-summary.json" and [p["entry_id"] for p in profiles["entries"]]==ids
required={"identity","glyph","source","claimed_description","practical_applications","practitioner_stories","evidence_and_limits","recovery"}
for e in entries:
 assert len(e.get("description_claim","")) <= 1000, f"description unexpectedly long: {e.get('entry_id')}"
for i,p in enumerate(profiles["entries"]):
 e=entries[i]
 assert required<=set(p["blocks"]) and (ROOT/"api/v1/bukovy"/f"{p['entry_id']}.json").is_file()
 s=summary["entries"][i]
 assert p["entry_id"]==s["entry_id"] and p.get("name")==s["name"]
 assert len(p["blocks"].get("practical_applications",[]))==s["counts"]["practical_applications"]
 assert len(p["blocks"].get("practitioner_stories",[]))==s["counts"]["practitioner_stories"]
 assert p["blocks"]["claimed_description"]["text"]==s["claimed_description"]["text"]
 if e.get("description_display") is not None:
  assert p["blocks"]["claimed_description"].get("display_text")==e["description_display"], f"display_text mismatch: {p['entry_id']}"
  assert s["claimed_description"].get("display_text")==e["description_display"], f"summary display_text mismatch: {p['entry_id']}"
 else:
  assert "display_text" not in p["blocks"]["claimed_description"], f"unexpected display_text: {p['entry_id']}"
  assert "display_text" not in s["claimed_description"], f"unexpected summary display_text: {p['entry_id']}"
 if p["blocks"]["claimed_description"].get("display_text") is not None:
  assert len(p["blocks"]["claimed_description"]["display_text"])<=1000
 individual=load(Path("api/v1/bukovy")/f"{p['entry_id']}.json")
 assert individual==p
story_ids=[s.get("story_id") for s in histories.get("stories",[])]; assert all(story_ids) and len(story_ids)==len(set(story_ids))
for s in histories.get("stories",[]): assert s.get("action") and s.get("reported_result") and s.get("source_urls")
print(f"PASS: {len(entries)} canonical Bukovy, {len(profiles['entries'])} per-Bukova profiles, {len(story_ids)} practitioner histories; {data['coverage']['unfilled_claimed_slots']} claimed slots still unfilled.")
