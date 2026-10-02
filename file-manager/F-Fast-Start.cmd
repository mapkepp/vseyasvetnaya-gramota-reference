@echo off
setlocal
set "BASE=%LOCALAPPDATA%\F-Fast-Bridge"
set "PS1=%BASE%\fast-bridge.ps1"
if not exist "%BASE%" mkdir "%BASE%" >nul 2>&1

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$u='https://raw.githubusercontent.com/mapkepp/vseyasvetnaya-gramota-reference/main/file-manager-fast/fast-bridge.ps1';$p=$env:LOCALAPPDATA+'\F-Fast-Bridge\fast-bridge.ps1';try{Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $p -ErrorAction Stop}catch{exit 10};try{$r=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 1 -ErrorAction Stop;if($r.StatusCode -eq 200){exit 0}}catch{};Start-Process powershell.exe -WindowStyle Hidden -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',$p;Start-Sleep -Milliseconds 700"
if errorlevel 10 (
  echo Не удалось получить ускоритель с GitHub.
  pause
  exit /b 10
)

start "" "https://mapkepp.github.io/vseyasvetnaya-gramota-reference/file-manager/?magic=1"
exit /b 0
