#!/usr/bin/env python3
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; api=ROOT/"api"/"v1"; profile_dir=api/"bukovy"; api.mkdir(parents=True,exist_ok=True); profile_dir.mkdir(parents=True,exist_ok=True)
bukovy=json.loads((ROOT/"data"/"bukovy.json").read_text("utf-8")); practices=json.loads((ROOT/"data"/"practices.json").read_text("utf-8")); histories=json.loads((ROOT/"data"/"practice"/"practitioner-histories.json").read_text("utf-8"))
for old in profile_dir.glob("*.json"): old.unlink()
def norm(v): return re.sub(r"\s+"," ",str(v or "").strip()).casefold()
def pm(n,pn):
 a,b=norm(n),norm(pn)
 if not a or not b:return False
 if a==b:return True
 aliases=[norm(x) for x in re.split(r"\s*/\s*|\s*,\s*",pn) if norm(x)]
 return a in aliases or any(a in x.split(" ") for x in aliases)
def sm(n,rel):
 a=norm(n)
 return any(a==norm(i) or (a and norm(i) and (a in norm(i) or norm(i) in a) and len(min(a,norm(i)))>=3) for i in (rel or []))
profiles=[]
for e in bukovy.get("entries",[]):
 lp=[p for p in practices.get("entries",[]) if pm(e.get("name"),p.get("name"))]; ls=[s for s in histories.get("stories",[]) if sm(e.get("name"),s.get("related_bukovy"))]
 claimed={"text":e.get("description_claim",""),"status":"source-published-claim"}
 if e.get("description_display") is not None: claimed["display_text"]=e["description_display"]
 p={"api_version":"v1","profile_version":"v1","entry_id":e["entry_id"],"name":e.get("name"),"data_status":{"catalog":"canonical-entry","practice":"linked" if lp else "no-linked-practice-record","stories":"linked" if ls else "no-linked-story-record"},"blocks":{"identity":{"name":e.get("name"),"entry_id":e["entry_id"],"source_image_number":e.get("source_image_number")},"glyph":{"image":e.get("image"),"image_status":e.get("image_status"),"source_image_url":e.get("source_image_url")},"source":{"source_url":e.get("source_url"),"source_id":e.get("source_id"),"claim_status":e.get("claim_status")},"claimed_description":claimed,"practical_applications":lp,"practitioner_stories":ls,"evidence_and_limits":{"catalog_note":"The description is preserved as a source-attributed claim.","practice_note":"Practical applications are secondary-source claims unless the linked record says otherwise.","story_note":"Practitioner stories are testimony and are not independent validation."},"recovery":{"claimed_total":bukovy.get("claimed_count"),"described_in_canonical_catalog":len(bukovy.get("entries",[])),"unfilled_claimed_slots":bukovy.get("coverage",{}).get("unfilled_claimed_slots")}}}
 profiles.append(p); (profile_dir/f"{e['entry_id']}.json").write_text(json.dumps(p,ensure_ascii=False,indent=2)+"\n","utf-8")
def summary(p):
 return {"api_version":"v1","summary_version":"v1","entry_id":p["entry_id"],"name":p["name"],"identity":p["blocks"]["identity"],"glyph":{"image":p["blocks"]["glyph"].get("image"),"image_status":p["blocks"]["glyph"].get("image_status"),"source_image_url":p["blocks"]["glyph"].get("source_image_url")},"source":p["blocks"]["source"],"claimed_description":p["blocks"]["claimed_description"],"data_status":p["data_status"],"counts":{"practical_applications":len(p["blocks"]["practical_applications"]),"practitioner_stories":len(p["blocks"]["practitioner_stories"])},"profile_url":f"/api/v1/bukovy/{p['entry_id']}.json"}
summary_doc={"api_version":"v1","summary_version":"v1","service":"bukovy-reference","status":"derived-from-canonical-catalog","description":"Lightweight per-Bukova index for fast clients; detailed blocks remain in individual profiles.","profile_count":len(profiles),"entries":[summary(p) for p in profiles]}
(api/"bukovy-summary.json").write_text(json.dumps(summary_doc,ensure_ascii=False,indent=2)+"\n","utf-8")
doc={"api_version":"v1","profile_version":"v1","service":"bukovy-reference","status":"derived-from-canonical-catalog","description":"Per-Bukova blocks joined from the canonical catalog, practical-application records, and practitioner stories.","profile_count":len(profiles),"entries":profiles}
(api/"bukovy-profiles.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n","utf-8")
index={"api_version":"v1","service":"bukovy-reference","description":"Static JSON API for the research reference catalog.","endpoints":{"bukovy":"/api/v1/bukovy.json","bukovy_profiles":"/api/v1/bukovy-profiles.json","bukovy_profile_template":"/api/v1/bukovy/{entry_id}.json","practices":"/api/v1/practices.json","practitioner_histories":"/api/v1/practitioner-histories.json","index":"/api/v1/index.json","schema":"/api/v1/bukovy.schema.json","bukovy_profile_schema":"/api/v1/bukovy-profile.schema.json","profile_manifest":"/api/v1/bukovy-manifest.json","profile_schema":"/api/v1/bukovy-profile.schema.json","bukovy_summary":"/api/v1/bukovy-summary.json"},"source_policy":"Catalog claims are attributed to their sources; missing claimed entries are not invented. Practitioner histories preserve reported actions and outcomes as unverified testimony. Per-Bukova profiles are derived joins and never replace the canonical catalog.","architecture":{"canonical":"/data/bukovy.json","derived_profile_collection":"/api/v1/bukovy-profiles.json","derived_profile":"/api/v1/bukovy/{entry_id}.json","join_sources":["/data/practices.json","/data/practice/practitioner-histories.json"],"design":"Bukova-first; every other block is linked to a canonical Bukova when source evidence permits."}}
manifest={"api_version":"v1","manifest_version":"v1","generated_from":"data/bukovy.json","profile_count":len(profiles),"entries":[e["entry_id"] for e in profiles],"template":"/api/v1/bukovy/{entry_id}.json","collection":"/api/v1/bukovy-profiles.json","cache_policy":"Immutable profile URLs by entry_id; clients may cache individual profiles aggressively. Summary, collection and index are refreshable.","summary":"/api/v1/bukovy-summary.json"}\nfor n,o in [("bukovy.json",bukovy),("practices.json",practices),("practitioner-histories.json",histories),("index.json",index),("bukovy-manifest.json",manifest)]: (api/n).write_text(json.dumps(o,ensure_ascii=False,indent=2)+"\n","utf-8")
print(f"API generated: {len(profiles)} per-Bukova profiles; {len(histories.get('stories',[]))} practitioner histories")
