@echo off
setlocal
set "BASE=%LOCALAPPDATA%\F-Fast-Bridge"
set "PS1=%BASE%\fast-bridge.ps1"
if not exist "%BASE%" mkdir "%BASE%" >nul 2>&1
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$u='https://raw.githubusercontent.com/mapkepp/vseyasvetnaya-gramota-reference/main/file-manager-fast/fast-bridge.ps1';$p=$env:LOCALAPPDATA+'\F-Fast-Bridge\fast-bridge.ps1';Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $p -ErrorAction Stop;try{$h=Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 1 -ErrorAction Stop;if($h.version -eq '3.0'){exit 0};Get-Process powershell -ErrorAction SilentlyContinue | Where-Object {$_.Path -and $_.CommandLine -and $_.CommandLine -like '*F-Fast-Bridge*'} | Stop-Process -Force -ErrorAction SilentlyContinue}catch{};Start-Process powershell.exe -WindowStyle Hidden -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',$p;Start-Sleep -Milliseconds 900"
start "" "https://mapkepp.github.io/vseyasvetnaya-gramota-reference/file-manager/?v=bridge30"
exit /b 0
