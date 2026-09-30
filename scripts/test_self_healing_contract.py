#!/usr/bin/env python3
"""Deterministic contract checks for the autonomous recovery loop."""
from pathlib import Path
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
watch=(ROOT/".github/workflows/research-watchdog.yml").read_text(encoding="utf-8")
repair=(ROOT/".github/workflows/system-self-repair.yml").read_text(encoding="utf-8")
worker=(ROOT/".github/workflows/autonomous-research-worker.yml").read_text(encoding="utf-8")
contract=json.loads((ROOT/"data/research/system-contract.json").read_text(encoding="utf-8"))

errors=[]
def need(text,label,needle):
    if needle not in text:
        errors.append(f"{label}: missing {needle}")

groups={}
for label,text in [("self-repair",repair),("worker",worker)]:
    m=re.search(r"concurrency:\s*\n\s*group:\s*([^\n]+)", text)
    if not m:
        errors.append(f"{label}: missing explicit concurrency group")
    else:
        groups[label]=m.group(1).strip()
if groups.get("self-repair") == groups.get("worker"):
    errors.append("recovery control-plane: worker and self-repair must use isolated concurrency groups")

for needle in ["repair_active","STALE_ACTIVE_WORKER","RECOVERY_NEEDED","WATCHDOG_WAIT",
               "actions/workflows/system-self-repair.yml/dispatches",
               "actions/workflows/autonomous-research-worker.yml/dispatches"]:
    need(watch,"watchdog",needle)
for needle in ["if: success()","SELF_REPAIR_PUBLISH_OK","SELF_REPAIR_PUBLISH_FAILED","SELF_REPAIR_HANDOFF"]:
    need(repair,"self-repair",needle)
for needle in ["Repair research queue before selection","git rebase --autostash origin/dev",
               "DEV_REBASE_CONFLICT","PUBLISH_OK","timeout=300","timeout=180"]:
    need(worker,"worker",needle)

if contract.get("state_writer_concurrency_group") != "dev-state-writers":
    errors.append("system-contract: shared writer group mismatch")
isolated=contract.get("isolated_recovery_groups", {})
if isolated.get("worker") != groups.get("worker") or isolated.get("self_repair") != groups.get("self-repair"):
    errors.append("system-contract: isolated recovery groups do not match workflows")

marker='if [ "$worker_active" -gt 0 ] && [ "$age" -gt 900 ]; then'
if marker not in watch:
    errors.append("watchdog: stale branch marker missing")
else:
    stale=watch.split(marker,1)[1].split("exit 0",1)[0]
    if "autonomous-research-worker.yml/dispatches" in stale:
        errors.append("watchdog: stale branch can dispatch worker with self-repair")

if "if: success()" not in repair or "SELF_REPAIR_PUBLISH_FAILED" not in repair:
    errors.append("self-repair: handoff is not fail-closed")

if errors:
    print("FAIL")
    print("\n".join("- "+e for e in errors))
    sys.exit(1)

print("PASS: autonomous recovery contract")
print("PASS: recovery workers use isolated concurrency groups")
print("PASS: stale worker -> self-repair -> worker handoff is fail-closed")
print("PASS: queue repair runs before worker selection")
