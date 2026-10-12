#!/usr/bin/env python3
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

FIRST = ROOT / "file-manager" / "index.html"
FAST = ROOT / "file-manager-fast" / "index.html"
BRIDGE = ROOT / "file-manager-fast" / "fast-bridge.ps1"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def script(html: str) -> str:
    m = re.search(r"<script>\n(.*?)\n</script>", html, re.S)
    if not m:
        raise AssertionError("script block not found")
    return m.group(1)

first_html = read(FIRST)
fast_html = read(FAST)
if not BRIDGE.read_bytes().startswith(bytes((239, 187, 191))):
    raise AssertionError("PowerShell 5.1 bridge source must be UTF-8 with BOM")
bridge = BRIDGE.read_text(encoding="utf-8-sig")

first = script(first_html)
fast = script(fast_html)

for needle in ("ROOT='MY-FILES'", "TOKEN_KEY='myfiles_token'"):
    if needle not in first:
        raise AssertionError(f"first page missing identity marker: {needle}")
for needle in ("ROOT='MY-FILES-FAST'", "TOKEN_KEY='myfiles_fast_token'"):
    if needle not in fast:
        raise AssertionError(f"fast page missing identity marker: {needle}")

first_norm = first.replace("ROOT='MY-FILES'", "ROOT='ROOT'").replace(
    "TOKEN_KEY='myfiles_token'", "TOKEN_KEY='TOKEN'"
).replace(
    "Подключено. MY-FILES доступна.", "Подключено. ROOT доступна."
)
fast_norm = fast.replace("ROOT='MY-FILES-FAST'", "ROOT='ROOT'").replace(
    "TOKEN_KEY='myfiles_fast_token'", "TOKEN_KEY='TOKEN'"
).replace(
    "Подключено. MY-FILES-FAST доступна.", "Подключено. ROOT доступна."
)

if first_norm != fast_norm:
    raise AssertionError("file-manager pages have diverged functional JavaScript cores")

if "<title>Мои файлы</title>" not in first_html or "<h1>📁 Мои файлы</h1>" not in first_html:
    raise AssertionError("first page header still contains F")
if "<title>F Мои файлы FAST</title>" not in fast_html or "<h1>F ⚡ Мои файлы FAST</h1>" not in fast_html:
    raise AssertionError("FAST page branding changed unexpectedly")

if "3 минуты" in first_html or "3 минуты" in fast_html:
    raise AssertionError("legacy 3-minute upload timeout remains")
if "localJson('http://127.0.0.1:8765/reserve',{method:'POST'},15_000)" not in first or "localJson('http://127.0.0.1:8765/reserve',{method:'POST'},15_000)" not in fast:
    raise AssertionError("reserve timeout protection missing")
if "21600" not in first or "21600" not in fast:
    raise AssertionError("large-file wait budget missing")

for needle in ("$BridgeVersion = '3.3'", "-TimeoutSec 15", "$req.Timeout=7200000", "/reserve", "/upload"):
    if needle not in bridge:
        raise AssertionError(f"bridge hardening marker missing: {needle}")

for marker in ("-not $listener.Pending()", "$reservationClock.Elapsed.TotalSeconds -lt $ReservationTimeoutSeconds", "[ValidateRange(1,600)][int]$ReservationTimeoutSeconds = 90"):
    if marker not in bridge:
        raise AssertionError(f"multi-connection reservation guard missing: {marker}")

print("PASS file-manager static contract")
print("PASS both pages have identical normalized functional core")
print("PASS first page has no F branding")
print("PASS FAST branding is preserved")
print("PASS reserve timeout and long upload wait are present")
print("PASS bridge 3.3 timeout/retry/reserve markers are present")
print("PASS reservation survives multiple health checks and has bounded wait")\nprint("PASS PowerShell 5.1 UTF-8 BOM is present")
