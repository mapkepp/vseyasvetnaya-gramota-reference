param(
  [switch]$Worker,
  [string]$JobFile,
  [int]$Port = 8765,
  [switch]$SingleJob
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$BridgeVersion = '3.2'
[Net.ServicePointManager]::Expect100Continue = $false
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Repo = 'mapkepp/-ai-private-toolbox'
$Base = Join-Path $env:LOCALAPPDATA 'F-Fast-Bridge'
$JobsDir = Join-Path $Base 'jobs'
$ScriptPath = $MyInvocation.MyCommand.Path
$ApiVersion = '2026-03-10'

New-Item -ItemType Directory -Force -Path $JobsDir | Out-Null

function Write-State {
  param([string]$Path,[hashtable]$State)
  [IO.File]::WriteAllText($Path,($State | ConvertTo-Json -Depth 10 -Compress),(New-Object Text.UTF8Encoding($false)))
}
function Read-State {
  param([string]$Path)
  if(-not(Test-Path -LiteralPath $Path)){return $null}
  return (Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json)
}
function Fail-Job {
  param([string]$Path,[string]$Message)
  Write-State $Path @{ok=$false;state='error';phase='ERROR';message=$Message;finishedAt=(Get-Date).ToString('o')}
}
function Encode-AssetName {
  param([string]$RelativePath)
  $b=[Text.Encoding]::UTF8.GetBytes($RelativePath)
  $s=[Convert]::ToBase64String($b).TrimEnd('=').Replace('+','-').Replace('/','_')
  return 'MF_'+$s
}
function Decode-Header {
  param([string]$Value)
  if([string]::IsNullOrWhiteSpace($Value)){return ''}
  return [Uri]::UnescapeDataString($Value)
}
function Api-Headers {
  param([string]$Token)
  return @{
    Authorization='Bearer '+$Token
    Accept='application/vnd.github+json'
    'X-GitHub-Api-Version'=$ApiVersion
  }
}
function Invoke-Api {
  param([string]$Method,[string]$Url,[string]$Token,[object]$Body=$null)
  $h=Api-Headers $Token
  if($null -ne $Body){
    return Invoke-RestMethod -Method $Method -Uri $Url -Headers $h -TimeoutSec 15 -Body ($Body|ConvertTo-Json -Depth 12) -ContentType 'application/json' -TimeoutSec 15
  }
  return Invoke-RestMethod -Method $Method -Uri $Url -Headers $h
}
function Get-Release {
  param([string]$Tag,[string]$Token)
  try { return Invoke-Api 'GET' ("https://api.github.com/repos/"+$Repo+"/releases/tags/"+[Uri]::EscapeDataString($Tag)) $Token }
  catch {
    $code=0
    if($_.Exception.Response){$code=$_.Exception.Response.StatusCode.value__}
    if($code -eq 404){return $null}
    throw
  }
}
function Ensure-Release {
  param([string]$Tag,[string]$Token)
  $r=Get-Release $Tag $Token
  if($r){return $r}
  return Invoke-Api 'POST' ("https://api.github.com/repos/"+$Repo+"/releases") $Token @{
    tag_name=$Tag;name=$Tag;body='Private binary storage';draft=$false;prerelease=$true
  }
}
function Get-Assets {
  param([object]$Release,[string]$Token)
  $all=@()
  for($page=1;$page -le 20;$page++){
    $xs=Invoke-Api 'GET' ("https://api.github.com/repos/"+$Repo+"/releases/"+$Release.id+"/assets?per_page=100&page="+$page) $Token
    if($null -eq $xs){break}
    $all+=@($xs)
    if(@($xs).Count -lt 100){break}
  }
  return $all
}
function Find-Asset {
  param([object]$Release,[string]$Name,[string]$Token)
  foreach($a in @(Get-Assets $Release $Token)){if($a.name -eq $Name){return $a}}
  return $null
}
function Delete-Asset {
  param([object]$Asset,[string]$Token)
  Invoke-Api 'DELETE' ("https://api.github.com/repos/"+$Repo+"/releases/assets/"+$Asset.id) $Token | Out-Null
}
function Upload-Binary {
  param([object]$Release,[string]$FilePath,[string]$AssetName,[string]$Token,[string]$StatePath,[int64]$Size)
  $url=$Release.upload_url -replace '\{\?name,label\}',('?name='+[Uri]::EscapeDataString($AssetName))
  $req=[Net.HttpWebRequest]::Create($url)
  $req.Method='POST'
  $req.ContentType='application/octet-stream'
  $req.ContentLength=$Size
  $req.Timeout=7200000
  $req.ReadWriteTimeout=7200000
  $req.AllowWriteStreamBuffering=$false
  $req.SendChunked=$false
  $req.KeepAlive=$false
  $req.Proxy=$null
  $req.Headers['Authorization']='Bearer '+$Token
  $req.Headers['Accept']='application/vnd.github+json'
  $req.Headers['X-GitHub-Api-Version']=$ApiVersion

  $input=[IO.File]::OpenRead($FilePath)
  $output=$null
  try{
    $output=$req.GetRequestStream()
    $buffer=New-Object byte[] 1048576
    [int64]$sent=0
    $started=Get-Date
    $last=$started
    while(($n=$input.Read($buffer,0,$buffer.Length)) -gt 0){
      $output.Write($buffer,0,$n)
      $sent+=$n
      $now=Get-Date
      if(($now-$last).TotalMilliseconds -ge 500){
        $sec=[math]::Max(.001,($now-$started).TotalSeconds)
        $speed=$sent/$sec
        $pct=[math]::Min(99,[math]::Floor(($sent*100.0)/$Size))
        Write-State $StatePath @{
          ok=$true;state='running';phase='GITHUB_UPLOAD';message='Передача в GitHub'
          size=$Size;sent=$sent;percent=$pct;speed=[math]::Round($speed,0);startedAt=$started.ToString('o')
        }
        $last=$now
      }
    }
  }finally{
    if($output){$output.Dispose()}
    $input.Dispose()
  }
  try{
    $resp=$req.GetResponse()
  }catch [Net.WebException]{
    $code=0
    if($_.Exception.Response){$code=$_.Exception.Response.StatusCode.value__}
    $detail=$_.Exception.Message
    if($_.Exception.Response){
      try{
        $sr=New-Object IO.StreamReader($_.Exception.Response.GetResponseStream())
        $body=$sr.ReadToEnd();$sr.Dispose()
        if($body){$detail=$detail+' · '+$body}
      }catch{}
    }
    throw ('GitHub asset upload HTTP '+$code+': '+$detail)
  }
  try{
    $reader=New-Object IO.StreamReader($resp.GetResponseStream())
    $txt=$reader.ReadToEnd();$reader.Dispose()
    if([string]::IsNullOrWhiteSpace($txt)){throw 'GitHub не вернул данные загруженного asset'}
    return ($txt|ConvertFrom-Json)
  }finally{$resp.Dispose()}
}

function Invoke-UploadJob {
  param([hashtable]$Job)
  $statePath=$Job.statePath
  $source=$Job.sourcePath
  $token=$Job.token
  $tag=$Job.tag
  $size=[int64]$Job.size
  $assetName=$Job.assetName
  $startedAt=$Job.startedAt
  try{
    if([string]::IsNullOrWhiteSpace($token)){throw 'Токен не передан'}
    Write-State $statePath @{
      ok=$true;state='running';phase='CHECK_RELEASE';message='Проверяю Release'
      size=$size;sent=$size;percent=0;startedAt=$startedAt
    }
    $release=Ensure-Release $tag $token
    $asset=$null
    for($attempt=1;$attempt -le 3;$attempt++){
      try{
        $release=Get-Release $tag $token
        $old=Find-Asset $release $assetName $token
        if($old){Delete-Asset $old $token}
        Write-State $statePath @{
          ok=$true;state='running';phase='GITHUB_UPLOAD'
          message=('Передаю бинарные данные в GitHub · попытка '+$attempt+'/3')
          size=$size;sent=0;percent=0;attempt=$attempt;startedAt=$startedAt
        }
        $asset=Upload-Binary $release $source $assetName $token $statePath $size
        if([int64]$asset.size -ne $size){throw 'GitHub сообщил несовпадающий размер'}
        break
      }catch{
        if($attempt -ge 3){throw}
        Write-State $statePath @{
          ok=$true;state='running';phase='RETRY'
          message=('Ошибка передачи, повтор через 5 секунд · попытка '+$attempt+'/3')
          size=$size;sent=0;percent=0;attempt=$attempt;startedAt=$startedAt
        }
        Start-Sleep -Seconds 5
      }
    }
    Write-State $statePath @{
      ok=$true;state='running';phase='VERIFY';message='Проверяю загруженный asset'
      size=$size;sent=$size;percent=99;startedAt=$startedAt
    }
    $release=Get-Release $tag $token
    $final=Find-Asset $release $assetName $token
    if(-not $final){throw 'Загруженный asset не найден'}
    if([int64]$final.size -ne $size -or $final.state -ne 'uploaded'){throw 'Проверка asset не пройдена'}
    Write-State $statePath @{
      ok=$true;state='done';phase='DONE';message='Файл сохранён и проверен'
      size=$size;sent=$size;percent=100;assetId=[int64]$final.id
      downloadUrl=$final.browser_download_url;finishedAt=(Get-Date).ToString('o')
    }
  }catch{
    Fail-Job $statePath $_.Exception.Message
  }finally{
    if($source){Remove-Item -LiteralPath $source -Force -ErrorAction SilentlyContinue}
  }
}
if($Worker){
  # Legacy mode intentionally disabled: tokens must never be read from job files.
  exit 3
}

function Send-Response {
  param([Net.Sockets.NetworkStream]$Stream,[int]$Status,[string]$ContentType,[string]$Body)
  $bytes=[Text.Encoding]::UTF8.GetBytes($Body)
  $reason=@{200='OK';201='Created';204='No Content';400='Bad Request';404='Not Found';413='Payload Too Large';500='Internal Server Error'}[$Status]
  if(-not $reason){$reason='OK'}
  $crlf=[char]13+[char]10
  $headers='HTTP/1.1 '+$Status+' '+$reason+$crlf+
    'Content-Type: '+$ContentType+'; charset=utf-8'+$crlf+
    'Content-Length: '+$bytes.Length+$crlf+
    'Access-Control-Allow-Origin: https://mapkepp.github.io'+$crlf+
    'Access-Control-Allow-Methods: GET,POST,OPTIONS'+$crlf+
    'Access-Control-Allow-Headers: Content-Type,Authorization,X-Tag,X-Rel-Path,X-Filename'+$crlf+
    'Access-Control-Allow-Private-Network: true'+$crlf+
    'Access-Control-Max-Age: 600'+$crlf+
    'Cache-Control: no-store'+$crlf+
    'Connection: close'+$crlf+$crlf
  $hb=[Text.Encoding]::ASCII.GetBytes($headers)
  $Stream.Write($hb,0,$hb.Length)
  if($bytes.Length -gt 0){$Stream.Write($bytes,0,$bytes.Length)}
}
function Read-Request {
  param([Net.Sockets.NetworkStream]$Stream)
  $list=New-Object Collections.Generic.List[byte]
  while($true){
    $b=$Stream.ReadByte()
    if($b -lt 0){break}
    $list.Add([byte]$b)
    $n=$list.Count
    if($n -ge 4 -and $list[$n-4] -eq 13 -and $list[$n-3] -eq 10 -and $list[$n-2] -eq 13 -and $list[$n-1] -eq 10){break}
    if($n -gt 65536){throw 'Слишком большой HTTP-заголовок'}
  }
  $crlf=[char]13+[char]10
  $txt=[Text.Encoding]::ASCII.GetString($list.ToArray())
  $lines=$txt -split $crlf
  $first=$lines[0] -split ' '
  $h=@{}
  if($lines.Count -gt 2){
    foreach($line in $lines[1..($lines.Count-2)]){
      $k=$line.IndexOf(':')
      if($k -gt 0){$h[$line.Substring(0,$k).Trim().ToLowerInvariant()]=$line.Substring($k+1).Trim()}
    }
  }
  return @{Method=$first[0];Path=$first[1];Headers=$h}
}
function Handle-Client {
  param([Net.Sockets.TcpClient]$Client)
  $stream=$Client.GetStream();$stream.ReadTimeout=120000;$stream.WriteTimeout=120000;$req=Read-Request $stream
  if($req.Method -eq 'OPTIONS'){Send-Response $stream 204 'text/plain' '';return}
  if($req.Method -eq 'GET'){
    if($req.Path -eq '/health'){Send-Response $stream 200 'application/json' (@{ok=$true;port=$Port;version=$BridgeVersion;single=$SingleJob.IsPresent}|ConvertTo-Json -Compress);return}
    if($req.Path -like '/status*'){
      $q=$req.Path.IndexOf('?');$query=if($q -ge 0){$req.Path.Substring($q+1)}else{''}
      $m=$query -split '&'|Where-Object{$_ -like 'id=*'}|Select-Object -First 1
      $id=if($m){$m.Substring(3)}else{''}
      if($id -and $id -match '^[a-f0-9]{32}$'){
        $sf=Join-Path $JobsDir ($id+'.status.json')
        if(Test-Path $sf){Send-Response $stream 200 'application/json' (Get-Content -Raw -LiteralPath $sf);return}
      }
      Send-Response $stream 404 'application/json' '{"ok":false,"message":"status not found"}';return
    }
    Send-Response $stream 404 'application/json' '{"ok":false,"message":"not found"}';return
  }
  if($req.Method -eq 'POST' -and $req.Path -eq '/reserve' -and -not $SingleJob){
    $newPort=0
    for($try=0;$try -lt 40;$try++){
      $candidate=Get-Random -Minimum 8800 -Maximum 8990
      $probe=$null
      try{
        $probe=New-Object Net.Sockets.TcpListener([Net.IPAddress]::Parse('127.0.0.1'),$candidate)
        $probe.Start();$probe.Stop();$probe=$null
        $newPort=$candidate
        break
      }catch{
        if($probe){try{$probe.Stop()}catch{}}
      }
    }
    if($newPort -eq 0){Send-Response $stream 500 'application/json' '{"ok":false,"message":"Не удалось найти свободный порт"}';return}

    Start-Process -FilePath 'powershell.exe' -WindowStyle Hidden -ArgumentList @(
      '-NoProfile','-ExecutionPolicy','Bypass','-File',$ScriptPath,'-SingleJob','-Port',$newPort
    )|Out-Null

    $ready=$false
    for($try=0;$try -lt 30;$try++){
      Start-Sleep -Milliseconds 100
      try{
        $h=Invoke-WebRequest -UseBasicParsing -Uri ('http://127.0.0.1:'+ $newPort +'/health') -TimeoutSec 1 -ErrorAction Stop
        if($h.StatusCode -eq 200){$ready=$true;break}
      }catch{}
    }
    if(-not $ready){Send-Response $stream 500 'application/json' (@{ok=$false;message='Локальный канал не запустился';port=$newPort}|ConvertTo-Json -Compress);return}
    Send-Response $stream 200 'application/json' (@{ok=$true;port=$newPort;version='+$BridgeVersion+'}|ConvertTo-Json -Compress)
    return
  }

  if($req.Method -eq 'POST' -and $req.Path -eq '/upload' -and $SingleJob){
    $auth=$req.Headers['authorization']
    if(-not $auth){Send-Response $stream 400 'application/json' '{"ok":false,"message":"missing authorization"}';return}
    $token=$auth -replace '^Bearer\\s+',''
    $tag=Decode-Header $req.Headers['x-tag']
    $rel=Decode-Header $req.Headers['x-rel-path']
    [int64]$size=0
    [void][int64]::TryParse($req.Headers['content-length'],[ref]$size)
    if($tag -notin @('MY-FILES','MY-FILES-FAST')){Send-Response $stream 400 'application/json' '{"ok":false,"message":"bad storage"}';return}
    if($size -le 0){Send-Response $stream 400 'application/json' '{"ok":false,"message":"empty file"}';return}
    if($size -ge 2147483648){Send-Response $stream 413 'application/json' '{"ok":false,"message":"file too large"}';return}
    if([string]::IsNullOrWhiteSpace($rel)){$rel=Decode-Header $req.Headers['x-filename']}
    $rel=$rel.Replace('\','/').TrimStart('/')
    if([string]::IsNullOrWhiteSpace($rel)){Send-Response $stream 400 'application/json' '{"ok":false,"message":"missing file name"}';return}

    $id=[guid]::NewGuid().ToString('N')
    $jobDir=Join-Path $JobsDir $id
    New-Item -ItemType Directory -Force -Path $jobDir|Out-Null
    $source=Join-Path $jobDir 'source.bin'
    $statePath=Join-Path $JobsDir ($id+'.status.json')
    try{
      $file=[IO.File]::Open($source,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
      try{
        $remaining=$size
        $received=[int64]0
        $buffer=New-Object byte[] 1048576
        while($remaining -gt 0){
          $read=$stream.Read($buffer,0,[int][math]::Min($buffer.Length,$remaining))
          if($read -le 0){throw 'Браузер оборвал передачу'}
          $file.Write($buffer,0,$read)
          $remaining-=$read
          $received+=$read
        }
      }finally{$file.Dispose()}

      $started=(Get-Date).ToString('o')
      Write-State $statePath @{
        ok=$true;state='running';phase='QUEUED'
        message='Файл полностью принят; начинаю передачу в GitHub'
        size=$size;sent=$size;percent=0;startedAt=$started
      }
      $script:PendingJob=@{
        statePath=$statePath
        sourcePath=$source
        assetName=(Encode-AssetName $rel)
        tag=$tag
        token=$token
        relativePath=$rel
        size=$size
        startedAt=$started
      }
      Send-Response $stream 201 'application/json' (@{ok=$true;id=$id}|ConvertTo-Json -Compress)
      return
    }catch{
      try{Fail-Job $statePath $_.Exception.Message}catch{}
      if(Test-Path -LiteralPath $source){Remove-Item -LiteralPath $source -Force -ErrorAction SilentlyContinue}
      throw
    }
  }
  Send-Response $stream 404 'application/json' '{"ok":false,"message":"not found"}'
}

$listener=New-Object Net.Sockets.TcpListener([Net.IPAddress]::Parse('127.0.0.1'),$Port)
$listener.Start()

if($SingleJob){
  Write-Host ('F-Fast Bridge 3.2 single upload: http://127.0.0.1:'+ $Port)
  $script:PendingJob=$null
  try{
    $client=$listener.AcceptTcpClient()
    try{Handle-Client $client}
    catch{
      try{Send-Response $client.GetStream() 500 'application/json' (@{ok=$false;message=$_.Exception.Message}|ConvertTo-Json -Compress)}catch{}
    }finally{$client.Close()}
  }finally{$listener.Stop()}
  if($script:PendingJob){
    Invoke-UploadJob $script:PendingJob
  }
  exit
}
Write-Host ('F-Fast Bridge 3.2 manager: http://127.0.0.1:'+ $Port)
while($true){
  $client=$listener.AcceptTcpClient()
  try{Handle-Client $client}
  catch{
    try{Send-Response $client.GetStream() 500 'application/json' (@{ok=$false;message=$_.Exception.Message}|ConvertTo-Json -Compress)}catch{}
  }finally{$client.Close()}
}
