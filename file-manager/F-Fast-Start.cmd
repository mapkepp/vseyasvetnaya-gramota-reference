@echo off
setlocal
set "BASE=%LOCALAPPDATA%\F-Fast-Bridge"
set "PS1=%BASE%\fast-bridge.ps1"
if not exist "%BASE%" mkdir "%BASE%" >nul 2>&1
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$u='https://raw.githubusercontent.com/mapkepp/vseyasvetnaya-gramota-reference/main/file-manager-fast/fast-bridge.ps1?v=31';$p=$env:LOCALAPPDATA+'\F-Fast-Bridge\fast-bridge.ps1';Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $p -ErrorAction Stop;$needStart=$true;try{$h=Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 1 -ErrorAction Stop;if($h.version -eq '3.1'){$needStart=$false}else{Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {$_.Name -match '^powershell(.exe)?$' -and $_.CommandLine -like '*F-Fast-Bridge*'} | ForEach-Object {Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue};Start-Sleep -Milliseconds 300}}catch{};if($needStart){Start-Process powershell.exe -WindowStyle Hidden -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',$p;Start-Sleep -Milliseconds 900}"
start "" "https://mapkepp.github.io/vseyasvetnaya-gramota-reference/file-manager/?v=bridge32"
exit /b 0
