param(
  [switch]$Worker,
  [string]$JobFile,
  [int]$Port = 8765
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Repo = 'mapkepp/-ai-private-toolbox'
$Base = Join-Path $env:LOCALAPPDATA 'F-Fast-Bridge'
$JobsDir = Join-Path $Base 'jobs'
$ScriptPath = $MyInvocation.MyCommand.Path

New-Item -ItemType Directory -Force -Path $JobsDir | Out-Null

function Write-State {
  param([string]$Path, [hashtable]$State)
  [IO.File]::WriteAllText(
    $Path,
    ($State | ConvertTo-Json -Depth 8 -Compress),
    (New-Object Text.UTF8Encoding($false))
  )
}

function Fail-Job {
  param([string]$Path, [string]$Message)
  Write-State $Path @{
    ok = $false
    state = 'error'
    phase = 'ERROR'
    message = $Message
    finishedAt = (Get-Date).ToString('o')
  }
}

function Encode-PathName {
  param([string]$Path)
  $bytes = [Text.Encoding]::UTF8.GetBytes($Path)
  $b64 = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
  return 'MF_' + $b64
}

function Get-Headers {
  param([string]$Token)
  return @{
    Authorization = 'Bearer ' + $Token
    Accept = 'application/vnd.github+json'
    'X-GitHub-Api-Version' = '2026-03-10'
  }
}

function Invoke-Api {
  param(
    [string]$Method,
    [string]$Url,
    [string]$Token,
    [object]$Body = $null
  )

  $headers = Get-Headers $Token

  if ($null -ne $Body) {
    return Invoke-RestMethod -Method $Method -Uri $Url -Headers $headers -Body ($Body | ConvertTo-Json -Depth 8) -ContentType 'application/json'
  }

  return Invoke-RestMethod -Method $Method -Uri $Url -Headers $headers
}

function Get-Release {
  param([string]$Tag, [string]$Token)

  try {
    return Invoke-Api 'GET' ("https://api.github.com/repos/" + $Repo + "/releases/tags/" + [Uri]::EscapeDataString($Tag)) $Token
  }
  catch {
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode.value__ -eq 404) {
      return $null
    }
    throw
  }
}

function Ensure-Release {
  param([string]$Tag, [string]$Token)

  $release = Get-Release $Tag $Token
  if ($release) { return $release }

  $body = @{
    tag_name = $Tag
    name = $Tag
    body = 'Private binary storage'
    draft = $false
    prerelease = $true
  }

  return Invoke-Api 'POST' ("https://api.github.com/repos/" + $Repo + "/releases") $Token $body
}

function Get-Assets {
  param([object]$Release, [string]$Token)

  $all = @()

  for ($page = 1; $page -le 20; $page++) {
    $items = Invoke-Api 'GET' ("https://api.github.com/repos/" + $Repo + "/releases/" + $Release.id + "/assets?per_page=100&page=" + $page) $Token
    if ($null -eq $items) { break }
    $all += $items
    if (@($items).Count -lt 100) { break }
  }

  return $all
}

function Find-Asset {
  param([object]$Release, [string]$Name, [string]$Token)

  foreach ($asset in @(Get-Assets $Release $Token)) {
    if ($asset.name -eq $Name) { return $asset }
  }

  return $null
}

function Upload-Asset {
  param(
    [object]$Release,
    [string]$FilePath,
    [string]$AssetName,
    [string]$Token,
    [string]$StatePath,
    [int64]$Size
  )

  $url = $Release.upload_url -replace '\{\?name,label\}', ('?name=' + [Uri]::EscapeDataString($AssetName))

  $request = [Net.HttpWebRequest]::Create($url)
  $request.Method = 'POST'
  $request.ContentType = 'application/octet-stream'
  $request.ContentLength = $Size
  $request.Timeout = 900000
  $request.ReadWriteTimeout = 900000
  $request.Headers['Authorization'] = 'Bearer ' + $Token
  $request.Headers['Accept'] = 'application/vnd.github+json'
  $request.Headers['X-GitHub-Api-Version'] = '2026-03-10'

  $input = [IO.File]::OpenRead($FilePath)
  $output = $null

  try {
    $output = $request.GetRequestStream()
    $buffer = New-Object byte[] 1048576
    [int64]$sent = 0
    $started = Get-Date
    $last = Get-Date

    while (($n = $input.Read($buffer, 0, $buffer.Length)) -gt 0) {
      $output.Write($buffer, 0, $n)
      $sent += $n

      $now = Get-Date
      if (($now - $last).TotalMilliseconds -ge 500) {
        $seconds = [math]::Max(0.001, ($now - $started).TotalSeconds)
        $speed = $sent / $seconds
        $percent = [math]::Min(99, [math]::Floor(($sent * 100.0) / $Size))

        Write-State $StatePath @{
          ok = $true
          state = 'running'
          phase = 'GITHUB_UPLOAD'
          message = 'Uploading binary data'
          size = $Size
          sent = $sent
          percent = $percent
          speed = [math]::Round($speed, 0)
          startedAt = $started.ToString('o')
        }

        $last = $now
      }
    }
  }
  finally {
    if ($output) { $output.Dispose() }
    $input.Dispose()
  }

  $response = $request.GetResponse()
  try {
    $reader = New-Object IO.StreamReader($response.GetResponseStream())
    $text = $reader.ReadToEnd()
    $reader.Dispose()
    return ($text | ConvertFrom-Json)
  }
  finally {
    $response.Dispose()
  }
}

function Delete-Asset {
  param([object]$Asset, [string]$Token)
  Invoke-Api 'DELETE' ("https://api.github.com/repos/" + $Repo + "/releases/assets/" + $Asset.id) $Token | Out-Null
}

function Rename-Asset {
  param([object]$Asset, [string]$NewName, [string]$Token)
  Invoke-Api 'PATCH' ("https://api.github.com/repos/" + $Repo + "/releases/assets/" + $Asset.id) $Token @{ name = $NewName } | Out-Null
}

if ($Worker) {
  if ([string]::IsNullOrWhiteSpace($JobFile)) { exit 2 }

  $source = $null
  $temp = $null
  $token = $null

  try {
    $job = Get-Content -Raw -LiteralPath $JobFile | ConvertFrom-Json
    $statePath = [IO.Path]::ChangeExtension($JobFile, '.status.json')
    $source = $job.sourcePath
    $token = $job.token
    $tag = $job.tag
    $size = [int64]$job.size
    $assetName = $job.assetName

    if ([string]::IsNullOrWhiteSpace($token)) { throw 'Missing token' }

    Write-State $statePath @{ ok = $true; state = 'running'; phase = 'CHECK_RELEASE'; message = 'Checking storage'; size = $size; sent = 0; percent = 0; startedAt = $job.startedAt }

    $release = Ensure-Release $tag $token
    $old = Find-Asset $release $assetName $token
    $tempName = 'MF_TMP_' + $job.id

    Write-State $statePath @{ ok = $true; state = 'running'; phase = 'GITHUB_UPLOAD'; message = 'Uploading binary data'; size = $size; sent = 0; percent = 0; startedAt = $job.startedAt }

    $temp = Upload-Asset $release $source $tempName $token $statePath $size

    if ([int64]$temp.size -ne $size) { throw 'Uploaded size mismatch' }

    Write-State $statePath @{ ok = $true; state = 'running'; phase = 'VERIFY'; message = 'Verifying upload'; size = $size; sent = $size; percent = 99; startedAt = $job.startedAt }

    $release = Get-Release $tag $token
    $temp = Find-Asset $release $tempName $token

    if (-not $temp) { throw 'Temporary asset not found' }
    if ([int64]$temp.size -ne $size) { throw 'Verified size mismatch' }

    if ($old) { Delete-Asset $old $token }
    Rename-Asset $temp $assetName $token

    $release = Get-Release $tag $token
    $final = Find-Asset $release $assetName $token

    if (-not $final) { throw 'Final asset not found' }
    if ([int64]$final.size -ne $size) { throw 'Final size mismatch' }

    Write-State $statePath @{
      ok = $true
      state = 'done'
      phase = 'DONE'
      message = 'File stored and verified'
      size = $size
      sent = $size
      percent = 100
      assetId = [int64]$final.id
      downloadUrl = $final.browser_download_url
      finishedAt = (Get-Date).ToString('o')
    }

    Remove-Item -LiteralPath $source -Force -ErrorAction SilentlyContinue
  }
  catch {
    $statePath = [IO.Path]::ChangeExtension($JobFile, '.status.json')
    Fail-Job $statePath $_.Exception.Message
    if ($source) { Remove-Item -LiteralPath $source -Force -ErrorAction SilentlyContinue }
    if ($temp -and $token) { try { Delete-Asset $temp $token } catch {} }
    exit 1
  }

  exit 0
}

function Send-Response {
  param([Net.Sockets.NetworkStream]$Stream,[int]$Status,[string]$ContentType,[string]$Body)

  $bytes = [Text.Encoding]::UTF8.GetBytes($Body)
  $reason = @{200='OK';201='Created';204='No Content';400='Bad Request';404='Not Found';413='Payload Too Large';500='Internal Server Error'}[$Status]
  $crlf = [char]13 + [char]10

  $headers = 'HTTP/1.1 ' + $Status + ' ' + $reason + $crlf +
    'Content-Type: ' + $ContentType + '; charset=utf-8' + $crlf +
    'Content-Length: ' + $bytes.Length + $crlf +
    'Access-Control-Allow-Origin: https://mapkepp.github.io' + $crlf +
    'Access-Control-Allow-Methods: GET,POST,OPTIONS' + $crlf +
    'Access-Control-Allow-Headers: Content-Type,Authorization,X-Tag,X-Filename,X-Rel-Path' + $crlf +
    'Cache-Control: no-store' + $crlf +
    'Connection: close' + $crlf + $crlf

  $headerBytes = [Text.Encoding]::ASCII.GetBytes($headers)
  $Stream.Write($headerBytes, 0, $headerBytes.Length)

  if ($bytes.Length -gt 0) {
    $Stream.Write($bytes, 0, $bytes.Length)
  }
}

function Read-Request {
  param([Net.Sockets.NetworkStream]$Stream)

  $list = New-Object Collections.Generic.List[byte]

  while ($true) {
    $b = $Stream.ReadByte()
    if ($b -lt 0) { break }
    $list.Add([byte]$b)
    $n = $list.Count

    if ($n -ge 4 -and $list[$n-4] -eq 13 -and $list[$n-3] -eq 10 -and $list[$n-2] -eq 13 -and $list[$n-1] -eq 10) {
      break
    }

    if ($n -gt 65536) { throw 'Header too large' }
  }

  $crlf = [char]13 + [char]10
  $text = [Text.Encoding]::ASCII.GetString($list.ToArray())
  $lines = $text -split $crlf
  $first = $lines[0] -split ' '
  $headers = @{}

  if ($lines.Count -gt 2) {
    foreach ($line in $lines[1..($lines.Count-2)]) {
      $k = $line.IndexOf(':')
      if ($k -gt 0) {
        $headers[$line.Substring(0,$k).Trim().ToLowerInvariant()] = $line.Substring($k+1).Trim()
      }
    }
  }

  return @{ Method = $first[0]; Path = $first[1]; Headers = $headers }
}

function Decode-Header {
  param([string]$Value)
  if ([string]::IsNullOrWhiteSpace($Value)) { return '' }
  return [Uri]::UnescapeDataString($Value)
}

function Handle-Client {
  param([Net.Sockets.TcpClient]$Client)

  $stream = $Client.GetStream()
  $req = Read-Request $stream

  if ($req.Method -eq 'OPTIONS') {
    Send-Response $stream 204 'text/plain' ''
    return
  }

  if ($req.Method -eq 'GET') {
    if ($req.Path -eq '/health') {
      Send-Response $stream 200 'application/json' (@{ ok = $true; port = $Port } | ConvertTo-Json -Compress)
      return
    }

    if ($req.Path -like '/status*') {
      $qmark = $req.Path.IndexOf('?')
      $query = if ($qmark -ge 0) { $req.Path.Substring($qmark + 1) } else { '' }
      $match = $query -split '&' | Where-Object { $_ -like 'id=*' } | Select-Object -First 1
      $id = if ($match) { $match.Substring(3) } else { '' }

      if ($id -and $id -match '^[a-f0-9]{32}$') {
        $stateFile = Join-Path $JobsDir ($id + '.status.json')
        if (Test-Path $stateFile) {
          Send-Response $stream 200 'application/json' (Get-Content -Raw -LiteralPath $stateFile)
          return
        }
      }

      Send-Response $stream 404 'application/json' '{"ok":false,"message":"not found"}'
      return
    }

    Send-Response $stream 404 'application/json' '{"ok":false,"message":"not found"}'
    return
  }

  if ($req.Method -eq 'POST' -and $req.Path -eq '/upload') {
    $auth = $req.Headers['authorization']

    if (-not $auth) {
      Send-Response $stream 400 'application/json' '{"ok":false,"message":"missing authorization"}'
      return
    }

    $token = $auth -replace '^Bearer\s+', ''
    $tag = Decode-Header $req.Headers['x-tag']
    $rel = Decode-Header $req.Headers['x-rel-path']
    $size = 0L

    if ($tag -notin @('MY-FILES','MY-FILES-FAST')) {
      Send-Response $stream 400 'application/json' '{"ok":false,"message":"bad storage"}'
      return
    }

    [void][int64]::TryParse($req.Headers['content-length'], [ref]$size)

    if ($size -le 0) {
      Send-Response $stream 400 'application/json' '{"ok":false,"message":"empty file"}'
      return
    }

    if ($size -gt 2147483648) {
      Send-Response $stream 413 'application/json' '{"ok":false,"message":"file too large"}'
      return
    }

    if ([string]::IsNullOrWhiteSpace($rel)) {
      $rel = Decode-Header $req.Headers['x-filename']
    }

    $rel = $rel.Replace('\','/').TrimStart('/')

    $id = [guid]::NewGuid().ToString('N')
    $jobDir = Join-Path $JobsDir $id
    New-Item -ItemType Directory -Force -Path $jobDir | Out-Null
    $source = Join-Path $jobDir 'source.bin'

    $file = [IO.File]::Open($source,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)

    try {
      $remaining = $size
      $buffer = New-Object byte[] 1048576

      while ($remaining -gt 0) {
        $read = $stream.Read($buffer,0,[int][math]::Min($buffer.Length,$remaining))
        if ($read -le 0) { throw 'client disconnected' }
        $file.Write($buffer,0,$read)
        $remaining -= $read
      }
    }
    finally {
      $file.Dispose()
    }

    $jobPath = Join-Path $JobsDir ($id + '.json')
    $job = @{
      id = $id
      sourcePath = $source
      assetName = Encode-PathName $rel
      tag = $tag
      token = $token
      relativePath = $rel
      size = $size
      startedAt = (Get-Date).ToString('o')
    }

    Write-State $jobPath $job
    Write-State (Join-Path $JobsDir ($id + '.status.json')) @{
      ok = $true
      state = 'queued'
      phase = 'QUEUED'
      message = 'Received from browser'
      size = $size
      sent = $size
      percent = 0
      startedAt = $job.startedAt
    }

    Start-Process -FilePath 'powershell.exe' -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File "' + $ScriptPath + '" -Worker -JobFile "' + $jobPath + '"') -WindowStyle Hidden | Out-Null

    Send-Response $stream 201 'application/json' (@{ ok = $true; id = $id } | ConvertTo-Json -Compress)
    return
  }

  Send-Response $stream 404 'application/json' '{"ok":false,"message":"not found"}'
}

$listener = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Parse('127.0.0.1'),$Port)
$listener.Start()

Write-Host 'F file bridge running on http://127.0.0.1:8765'
Write-Host 'Close this window to stop the bridge.'

while ($true) {
  $client = $listener.AcceptTcpClient()
  try {
    Handle-Client $client
  }
  catch {
    try {
      Send-Response $client.GetStream() 500 'application/json' (@{ ok = $false; message = $_.Exception.Message } | ConvertTo-Json -Compress)
    } catch {}
  }
  finally {
    $client.Close()
  }
}
