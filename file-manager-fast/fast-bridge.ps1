param(
  [switch]$Worker,
  [string]$JobFile,
  [int]$Port = 8765
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Repo = 'mapkepp/-ai-private-toolbox'
$Tag = 'MY-FILES-FAST'
$Base = Join-Path $env:LOCALAPPDATA 'F-Fast-Bridge'
$JobsDir = Join-Path $Base 'jobs'
$ScriptPath = $MyInvocation.MyCommand.Path
$NL = [Environment]::NewLine
New-Item -ItemType Directory -Force -Path $JobsDir | Out-Null

function Write-State {
  param([string]$Path,[hashtable]$State)
  [IO.File]::WriteAllText($Path,($State|ConvertTo-Json -Depth 6 -Compress),(New-Object Text.UTF8Encoding($false)))
}
function Fail-Job {
  param([string]$Path,[string]$Message)
  Write-State $Path @{ok=$false;state='error';phase='Ошибка';message=$Message;finishedAt=(Get-Date).ToString('o')}
}
function Encode-AssetName {
  param([string]$Path)
  $b=[Text.Encoding]::UTF8.GetBytes($Path)
  return 'MF_'+([Convert]::ToBase64String($b).TrimEnd('=').Replace('+','-').Replace('/','_'))
}
function Get-Gh {
  $c=Get-Command gh -ErrorAction SilentlyContinue
  if(!$c){throw 'GitHub CLI (gh) не найден в PATH.'}
  return $c.Source
}
function Ensure-Release {
  param([string]$Gh)
  & $Gh release view $Tag -R $Repo *> $null
  if($LASTEXITCODE -ne 0){
    & $Gh release create $Tag -R $Repo --title 'F Мои файлы FAST' --notes 'Бинарное файловое хранилище F Мои файлы FAST.' --prerelease --latest=false *> $null
    if($LASTEXITCODE -ne 0){throw 'Не удалось создать служебный релиз MY-FILES-FAST.'}
  }
  for($i=0;$i -lt 10;$i++){
    & $Gh release view $Tag -R $Repo *> $null
    if($LASTEXITCODE -eq 0){return}
    Start-Sleep -Milliseconds 800
  }
  throw 'GitHub создал релиз, но он ещё не виден API.'
}
function Get-Release {
  param([string]$Gh)
  $raw=& $Gh api "repos/$Repo/releases/tags/$Tag" 2>&1
  if($LASTEXITCODE -ne 0){throw (($raw -join $NL).Trim())}
  return ($raw -join $NL|ConvertFrom-Json)
}
function Get-AssetByName {
  param([string]$Gh,[long]$ReleaseId,[string]$Name)
  for($page=1;$page -le 10;$page++){
    $raw=& $Gh api "repos/$Repo/releases/$ReleaseId/assets?per_page=100&page=$page" 2>&1
    if($LASTEXITCODE -ne 0){throw (($raw -join $NL).Trim())}
    $arr=@($raw -join $NL|ConvertFrom-Json)
    if($arr.Count -eq 0){return $null}
    foreach($a in $arr){if($a.name -eq $Name){return $a}}
    if($arr.Count -lt 100){return $null}
  }
  return $null
}
function Upload-Binary {
  param([string]$Gh,[string]$SourcePath)
  $psi=New-Object Diagnostics.ProcessStartInfo
  $psi.FileName=$Gh
  $psi.UseShellExecute=$false
  $psi.CreateNoWindow=$true
  $psi.RedirectStandardOutput=$true
  $psi.RedirectStandardError=$true
  $psi.Arguments='release upload "'+$Tag+'" "'+$SourcePath+'" -R "'+$Repo+'"'
  $p=New-Object Diagnostics.Process
  $p.StartInfo=$psi
  [void]$p.Start()
  $started=Get-Date
  while(!$p.HasExited){Start-Sleep -Milliseconds 1000}
  $o=$p.StandardOutput.ReadToEnd();$e=$p.StandardError.ReadToEnd()
  return @{ExitCode=$p.ExitCode;Stdout=$o;Stderr=$e;Seconds=[math]::Round(((Get-Date)-$started).TotalSeconds,1)}
}
if($Worker){
  if([string]::IsNullOrWhiteSpace($JobFile)){exit 2}
  $sourcePath=$null;$tmpPath=$null;$tmpAsset=$null
  try{
    $job=Get-Content -Raw -LiteralPath $JobFile|ConvertFrom-Json
    $statePath=[IO.Path]::ChangeExtension($JobFile,'.status.json')
    $sourcePath=$job.sourcePath;$size=[int64]$job.size;$assetName=$job.assetName
    Write-State $statePath @{ok=$true;state='running';phase='Проверяю GitHub CLI';message='Начинаю бинарную загрузку…';size=$size;startedAt=$job.startedAt}
    $gh=Get-Gh
    & $gh auth status -h github.com *> $null
    if($LASTEXITCODE -ne 0){throw 'GitHub CLI не авторизован. Выполни gh auth login.'}
    Write-State $statePath @{ok=$true;state='running';phase='Готовлю хранилище';message='Проверяю служебный релиз…';size=$size;startedAt=$job.startedAt}
    Ensure-Release $gh
    $release=Get-Release $gh
    $target=Get-AssetByName $gh ([long]$release.id) $assetName
    $tmpName='MF_TMP_'+$job.id
    $tmpPath=Join-Path (Split-Path -Parent $sourcePath) $tmpName
    Rename-Item -LiteralPath $sourcePath -NewName $tmpName
    Write-State $statePath @{ok=$true;state='running';phase='Отправка в GitHub';message='Бинарная передача идёт через GitHub CLI без Base64…';size=$size;startedAt=$job.startedAt}
    $upload=Upload-Binary $gh $tmpPath
    if($upload.ExitCode -ne 0){
      $detail=$upload.Stderr.Trim();if([string]::IsNullOrWhiteSpace($detail)){$detail=$upload.Stdout.Trim()}
      $m='GitHub upload завершился с ошибкой.';if($detail){$m+=' '+$detail};throw $m
    }
    Write-State $statePath @{ok=$true;state='running';phase='Проверяю сохранение';message='Проверяю загруженный бинарный asset на стороне GitHub…';size=$size;startedAt=$job.startedAt;githubSeconds=$upload.Seconds}
    $release=Get-Release $gh
    $tmpAsset=Get-AssetByName $gh ([long]$release.id) $tmpName
    if(-not $tmpAsset){throw 'GitHub ответил об успешной загрузке, но временный asset не найден.'}
    if([int64]$tmpAsset.size -ne $size){throw ('Размер сохранённого asset не совпадает: '+$tmpAsset.size+' байт вместо '+$size+'.')}
    if($target){
      & $gh api --method DELETE "repos/$Repo/releases/assets/$($target.id)" *> $null
      if($LASTEXITCODE -ne 0){throw 'Новый файл загружен и проверен, но старую версию не удалось удалить.'}
    }
    $patchRaw=& $gh api --method PATCH "repos/$Repo/releases/assets/$($tmpAsset.id)" -f "name=$assetName" 2>&1
    if($LASTEXITCODE -ne 0){throw (($patchRaw -join $NL).Trim())}
    $release=Get-Release $gh
    $newAsset=Get-AssetByName $gh ([long]$release.id) $assetName
    if(-not $newAsset){throw 'После переименования asset не найден при повторной проверке.'}
    if([int64]$newAsset.size -ne $size){throw ('Финальный размер не совпадает: '+$newAsset.size+' байт вместо '+$size+'.')}
    Write-State $statePath @{ok=$true;state='done';phase='Готово';message='Файл записан и проверен в GitHub.';size=$size;githubSeconds=$upload.Seconds;assetId=[int64]$newAsset.id;downloadUrl=$newAsset.browser_download_url;finishedAt=(Get-Date).ToString('o')}
    if($tmpPath){Remove-Item -LiteralPath $tmpPath -Force -ErrorAction SilentlyContinue}
  }catch{
    $statePath=[IO.Path]::ChangeExtension($JobFile,'.status.json')
    try{if($tmpAsset){& $gh api --method DELETE "repos/$Repo/releases/assets/$($tmpAsset.id)" *> $null}}catch{}
    Fail-Job $statePath $_.Exception.Message
    if($sourcePath){Remove-Item -LiteralPath $sourcePath -Force -ErrorAction SilentlyContinue}
    if($tmpPath){Remove-Item -LiteralPath $tmpPath -Force -ErrorAction SilentlyContinue}
    exit 1
  }
  exit 0
}
function Send-Response {
  param([Net.Sockets.NetworkStream]$Stream,[int]$Status,[string]$Type,[string]$Body)
  $bytes=[Text.Encoding]::UTF8.GetBytes($Body)
  $reason=@{200='OK';201='Created';204='No Content';400='Bad Request';404='Not Found';413='Payload Too Large';500='Internal Server Error'}[$Status]
  $crlf=[char]13+[char]10
  $headers='HTTP/1.1 '+$Status+' '+$reason+$crlf+'Content-Type: '+$Type+'; charset=utf-8'+$crlf+'Content-Length: '+$bytes.Length+$crlf+'Access-Control-Allow-Origin: https://mapkepp.github.io'+$crlf+'Access-Control-Allow-Methods: GET,POST,OPTIONS'+$crlf+'Access-Control-Allow-Headers: Content-Type,X-Filename,X-Rel-Path'+$crlf+'Cache-Control: no-store'+$crlf+'Connection: close'+$crlf+$crlf
  $hb=[Text.Encoding]::ASCII.GetBytes($headers);$Stream.Write($hb,0,$hb.Length)
  if($bytes.Length -gt 0){$Stream.Write($bytes,0,$bytes.Length)}
}
function Read-Request {
  param([Net.Sockets.NetworkStream]$Stream)
  $list=New-Object Collections.Generic.List[byte]
  while($true){
    $b=$Stream.ReadByte();if($b -lt 0){break};$list.Add([byte]$b);$n=$list.Count
    if($n -ge 4 -and $list[$n-4] -eq 13 -and $list[$n-3] -eq 10 -and $list[$n-2] -eq 13 -and $list[$n-1] -eq 10){break}
    if($n -gt 65536){throw 'Слишком большой HTTP-заголовок.'}
  }
  $text=[Text.Encoding]::ASCII.GetString($list.ToArray());$crlf=[char]13+[char]10;$lines=$text -split $crlf;$parts=$lines[0] -split ' ';$headers=@{}
  if($lines.Count -gt 2){foreach($line in $lines[1..($lines.Count-2)]){$k=$line.IndexOf(':');if($k -gt 0){$headers[$line.Substring(0,$k).Trim().ToLowerInvariant()]=$line.Substring($k+1).Trim()}}}
  return @{Method=$parts[0];Path=$parts[1];Headers=$headers}
}
function Decode-Header {param([string]$Value) if([string]::IsNullOrWhiteSpace($Value)){return ''} return [Uri]::UnescapeDataString($Value)}
function Handle-Client {
  param([Net.Sockets.TcpClient]$Client)
  $stream=$Client.GetStream();$req=Read-Request $stream
  if($req.Method -eq 'OPTIONS'){Send-Response $stream 204 'text/plain' '';return}
  if($req.Method -eq 'GET'){
    if($req.Path -eq '/health'){Send-Response $stream 200 'application/json' (@{ok=$true;repo=$Repo;tag=$Tag;port=$Port}|ConvertTo-Json -Compress);return}
    if($req.Path -like '/status*'){
      $qmark=$req.Path.IndexOf('?');$query=if($qmark -ge 0){$req.Path.Substring($qmark+1)}else{''};$id=($query -split '&'|Where-Object{$_ -like 'id=*'}|Select-Object -First 1);if($id){$id=$id.Substring(3)}
      if(!$id -or $id -notmatch '^[a-f0-9]{32}$'){Send-Response $stream 400 'application/json' '{"ok":false,"message":"Неверный id"}';return}
      $sp=Join-Path $JobsDir ($id+'.status.json');if(!(Test-Path $sp)){Send-Response $stream 404 'application/json' '{"ok":false,"message":"Задание не найдено"}';return}
      Send-Response $stream 200 'application/json' (Get-Content -Raw -LiteralPath $sp);return
    }
    Send-Response $stream 404 'application/json' '{"ok":false,"message":"Not Found"}';return
  }
  if($req.Method -eq 'POST' -and $req.Path -eq '/upload'){
    $cl=0;[void][int64]::TryParse($req.Headers['content-length'],[ref]$cl)
    if($cl -le 0){Send-Response $stream 400 'application/json' '{"ok":false,"message":"Пустой файл"}';return}
    if($cl -gt 2147483648){Send-Response $stream 413 'application/json' '{"ok":false,"message":"Файл больше 2 GiB"}';return}
    $name=Decode-Header $req.Headers['x-filename'];$rel=Decode-Header $req.Headers['x-rel-path'];if([string]::IsNullOrWhiteSpace($name)){$name='file.bin'};if([string]::IsNullOrWhiteSpace($rel)){$rel=$name}
    $rel=$rel.Replace('\','/').TrimStart('/');$parts=$rel -split '/'
    if($parts.Count -gt 30 -or ($parts|Where-Object{$_ -eq '..' -or [string]::IsNullOrWhiteSpace($_)}).Count -gt 0){Send-Response $stream 400 'application/json' '{"ok":false,"message":"Недопустимый путь"}';return}
    $id=[guid]::NewGuid().ToString('N');$jobDir=Join-Path $JobsDir $id;New-Item -ItemType Directory -Force -Path $jobDir|Out-Null
    $assetName=Encode-AssetName $rel;$sourcePath=Join-Path $jobDir $assetName
    $out=[IO.File]::Open($sourcePath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try{$remaining=$cl;$buffer=New-Object byte[] 1048576;while($remaining -gt 0){$read=$stream.Read($buffer,0,[int][math]::Min($buffer.Length,$remaining));if($read -le 0){throw 'Клиент оборвал передачу до конца файла.'};$out.Write($buffer,0,$read);$remaining-=$read}}finally{$out.Dispose()}
    $jobPath=Join-Path $JobsDir ($id+'.json');$job=@{id=$id;sourcePath=$sourcePath;assetName=$assetName;relativePath=$rel;size=$cl;startedAt=(Get-Date).ToString('o')}
    Write-State $jobPath $job;$statusPath=Join-Path $JobsDir ($id+'.status.json');Write-State $statusPath @{ok=$true;state='queued';phase='Получен от браузера';message='Файл принят локальным мостом. Передаю в GitHub…';size=$cl;startedAt=$job.startedAt}
    $arg='-NoProfile -ExecutionPolicy Bypass -File "'+$ScriptPath+'" -Worker -JobFile "'+$jobPath+'"';Start-Process -FilePath 'powershell.exe' -ArgumentList $arg -WindowStyle Hidden|Out-Null
    Send-Response $stream 201 'application/json' (@{ok=$true;id=$id}|ConvertTo-Json -Compress);return
  }
  Send-Response $stream 404 'application/json' '{"ok":false,"message":"Not Found"}'
}
$listener=New-Object Net.Sockets.TcpListener([Net.IPAddress]::Parse('127.0.0.1'),$Port);$listener.Start()
Write-Host '';Write-Host 'F Мои файлы FAST — локальный ускоритель запущен.' -ForegroundColor Cyan;Write-Host ('http://127.0.0.1:'+ $Port);Write-Host ('Репозиторий: '+$Repo);Write-Host ('Хранилище: '+$Tag);Write-Host 'Закрой это окно, чтобы остановить ускоритель.';Write-Host ''
while($true){$client=$listener.AcceptTcpClient();try{Handle-Client $client}catch{try{Send-Response $client.GetStream() 500 'application/json' (@{ok=$false;message=$_.Exception.Message}|ConvertTo-Json -Compress)}catch{}}finally{$client.Close()}}
