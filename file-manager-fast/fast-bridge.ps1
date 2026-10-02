param([switch]$Worker,[string]$JobFile,[int]$Port=8765)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$Repo='mapkepp/-ai-private-toolbox'
$Base=Join-Path $env:LOCALAPPDATA 'F-Fast-Bridge'
$JobsDir=Join-Path $Base 'jobs'
$ScriptPath=$MyInvocation.MyCommand.Path
New-Item -ItemType Directory -Force -Path $JobsDir|Out-Null

function State([string]$p,[hashtable]$s){[IO.File]::WriteAllText($p,($s|ConvertTo-Json -Depth 8 -Compress),(New-Object Text.UTF8Encoding($false)))}
function Fail([string]$p,[string]$m){State $p @{ok=$false;state='error';phase='ERROR';message=$m;finishedAt=(Get-Date).ToString('o')}}
function Enc([string]$p){$b=[Text.Encoding]::UTF8.GetBytes($p);return 'MF_'+([Convert]::ToBase64String($b).TrimEnd('=').Replace('+','-').Replace('/','_'))}
function H([string]$t){@{Authorization=('Bearer '+$t);Accept='application/vnd.github+json';'X-GitHub-Api-Version'='2026-03-10'}}
function Api([string]$m,[string]$u,[string]$t,[object]$b=$null){$h=H $t;if($null -ne $b){return Invoke-RestMethod -Method $m -Uri $u -Headers $h -Body ($b|ConvertTo-Json -Depth 8) -ContentType 'application/json'}return Invoke-RestMethod -Method $m -Uri $u -Headers $h}
function Release([string]$tag,[string]$t){try{return Api GET ("https://api.github.com/repos/"+$Repo+"/releases/tags/"+[Uri]::EscapeDataString($tag)) $t}catch{if($_.Exception.Response -and $_.Exception.Response.StatusCode.value__ -eq 404){return $null};throw}}
function EnsureRelease([string]$tag,[string]$t){$r=Release $tag $t;if($r){return $r};return Api POST ("https://api.github.com/repos/"+$Repo+"/releases") $t @{tag_name=$tag;name=$tag;body='Private binary storage';draft=$false;prerelease=$true}}
function Assets([object]$r,[string]$t){$o=@();for($p=1;$p -le 20;$p++){$a=Api GET ("https://api.github.com/repos/"+$Repo+"/releases/"+$r.id+"/assets?per_page=100&page="+$p) $t;if(!$a){break};$o+=$a;if(@($a).Count -lt 100){break}}return $o}
function FindAsset([object]$r,[string]$n,[string]$t){foreach($a in @(Assets $r $t)){if($a.name -eq $n){return $a}}return $null}
function Upload([object]$r,[string]$file,[string]$name,[string]$t,[string]$sp,[int64]$size){
  $u=$r.upload_url -replace '\{\?name,label\}','?name='+[Uri]::EscapeDataString($name)
  $q=[Net.HttpWebRequest]::Create($u);$q.Method='POST';$q.ContentType='application/octet-stream';$q.ContentLength=$size;$q.Timeout=900000;$q.ReadWriteTimeout=900000
  $q.Headers['Authorization']='Bearer '+$t;$q.Headers['Accept']='application/vnd.github+json';$q.Headers['X-GitHub-Api-Version']='2026-03-10'
  $input=[IO.File]::OpenRead($file);$stream=$q.GetRequestStream()
  try{$buf=New-Object byte[] 1048576;$sent=0L;$last=Get-Date;$start=Get-Date;while(($n=$input.Read($buf,0,$buf.Length)) -gt 0){$stream.Write($buf,0,$n);$sent+=$n;$now=Get-Date;if(($now-$last).TotalMilliseconds -ge 500){$sec=[math]::Max(.001,($now-$start).TotalSeconds);State $sp @{ok=$true;state='running';phase='GITHUB_UPLOAD';message='Uploading binary data';size=$size;sent=$sent;percent=[math]::Min(99,[math]::Floor($sent*100/$size));speed=[math]::Round($sent/$sec,0);startedAt=(Get-Date).ToString('o')};$last=$now}}}finally{$stream.Dispose();$input.Dispose()}
  $resp=$q.GetResponse();try{$sr=New-Object IO.StreamReader($resp.GetResponseStream());$txt=$sr.ReadToEnd();$sr.Dispose();return ($txt|ConvertFrom-Json)}finally{$resp.Dispose()}
}
if($Worker){
  $source=$null;$token=$null;$tmp=$null
  try{
    $job=Get-Content -Raw -LiteralPath $JobFile|ConvertFrom-Json;$sp=[IO.Path]::ChangeExtension($JobFile,'.status.json');$source=$job.sourcePath;$token=$job.token;$tag=$job.tag;$size=[int64]$job.size;$name=$job.assetName
    State $sp @{ok=$true;state='running';phase='CHECK_RELEASE';message='Checking storage';size=$size;sent=0;percent=0;startedAt=$job.startedAt}
    $r=EnsureRelease $tag $token;$old=FindAsset $r $name $token;$tmpName='MF_TMP_'+$job.id
    State $sp @{ok=$true;state='running';phase='GITHUB_UPLOAD';message='Uploading binary data';size=$size;sent=0;percent=0;startedAt=$job.startedAt}
    $tmp=Upload $r $source $tmpName $token $sp $size
    if([int64]$tmp.size -ne $size){throw 'Uploaded size mismatch'}
    State $sp @{ok=$true;state='running';phase='VERIFY';message='Verifying upload';size=$size;sent=$size;percent=99;startedAt=$job.startedAt}
    $r=Release $tag $token;$tmp=FindAsset $r $tmpName $token;if(!$tmp){throw 'Temporary asset not found'}
    if([int64]$tmp.size -ne $size){throw 'Verified size mismatch'}
    if($old){Api DELETE ("https://api.github.com/repos/"+$Repo+"/releases/assets/"+$old.id) $token|Out-Null}
    Api PATCH ("https://api.github.com/repos/"+$Repo+"/releases/assets/"+$tmp.id) $token @{name=$name}|Out-Null
    $r=Release $tag $token;$final=FindAsset $r $name $token;if(!$final){throw 'Final asset not found'};if([int64]$final.size -ne $size){throw 'Final size mismatch'}
    State $sp @{ok=$true;state='done';phase='DONE';message='File stored and verified';size=$size;sent=$size;percent=100;assetId=[int64]$final.id;downloadUrl=$final.browser_download_url;finishedAt=(Get-Date).ToString('o')}
    Remove-Item -LiteralPath $source -Force -ErrorAction SilentlyContinue
  }catch{$sp=[IO.Path]::ChangeExtension($JobFile,'.status.json');Fail $sp $_.Exception.Message;if($source){Remove-Item -LiteralPath $source -Force -ErrorAction SilentlyContinue};if($tmp -and $token){try{Api DELETE ("https://api.github.com/repos/"+$Repo+"/releases/assets/"+$tmp.id) $token|Out-Null}catch{}};exit 1}
  exit 0
}
function Resp([Net.Sockets.NetworkStream]$s,[int]$code,[string]$type,[string]$body){$b=[Text.Encoding]::UTF8.GetBytes($body);$reason=@{200='OK';201='Created';204='No Content';400='Bad Request';404='Not Found';413='Payload Too Large';500='Internal Server Error'}[$code];$cr=[char]13+[char]10;$h='HTTP/1.1 '+$code+' '+$reason+$cr+'Content-Type: '+$type+'; charset=utf-8'+$cr+'Content-Length: '+$b.Length+$cr+'Access-Control-Allow-Origin: https://mapkepp.github.io'+$cr+'Access-Control-Allow-Methods: GET,POST,OPTIONS'+$cr+'Access-Control-Allow-Headers: Content-Type,Authorization,X-Tag,X-Filename,X-Rel-Path'+$cr+'Cache-Control: no-store'+$cr+'Connection: close'+$cr+$cr;$hb=[Text.Encoding]::ASCII.GetBytes($h);$s.Write($hb,0,$hb.Length);if($b.Length){$s.Write($b,0,$b.Length)}}
function Request([Net.Sockets.NetworkStream]$s){$l=New-Object Collections.Generic.List[byte];while($true){$b=$s.ReadByte();if($b-lt 0){break};$l.Add([byte]$b);$n=$l.Count;if($n-ge4-and$l[$n-4]-eq13-and$l[$n-3]-eq10-and$l[$n-2]-eq13-and$l[$n-1]-eq10){break};if($n-gt65536){throw 'Header too large'}};$cr=[char]13+[char]10;$txt=[Text.Encoding]::ASCII.GetString($l.ToArray());$lines=$txt-split$cr;$parts=$lines[0]-split' ';$hs=@{};if($lines.Count-gt2){foreach($line in $lines[1..($lines.Count-2)]){$k=$line.IndexOf(':');if($k-gt0){$hs[$line.Substring(0,$k).Trim().ToLowerInvariant()]=$line.Substring($k+1).Trim()}}};return @{Method=$parts[0];Path=$parts[1];Headers=$hs}}
function U([string]$v){if([string]::IsNullOrWhiteSpace($v)){return ''};return[Uri]::UnescapeDataString($v)}
function Handle([Net.Sockets.TcpClient]$c){$s=$c.GetStream();$r=Request $s;if($r.Method-eq'OPTIONS'){Resp $s 204 'text/plain' '';return};if($r.Method-eq'GET'){if($r.Path-eq'/health'){Resp $s 200 'application/json' (@{ok=$true;port=$Port}|ConvertTo-Json -Compress);return};if($r.Path-like'/status*'){$q=if($r.Path.IndexOf('?')-ge0){$r.Path.Substring($r.Path.IndexOf('?')+1)}else{''};$id=($q-split'&'|Where-Object{$_-like'id=*'}|Select-Object-First1);if($id){$id=$id.Substring(3)};$p=Join-Path $JobsDir ($id+'.status.json');if($id-and$id-match'^[a-f0-9]{32}$'-and(Test-Path $p)){Resp $s 200 'application/json' (Get-Content-Raw-LiteralPath$p);return};Resp $s 404 'application/json' '{"ok":false,"message":"not found"}';return};Resp $s 404 'application/json' '{"ok":false,"message":"not found"}';return}
if($r.Method-eq'POST'-and$r.Path-eq'/upload'){$auth=$r.Headers['authorization'];if(!$auth){Resp $s 400 'application/json' '{"ok":false,"message":"missing authorization"}';return};$token=$auth-replace'^Bearer\s+','';$tag=U $r.Headers['x-tag'];$rel=U $r.Headers['x-rel-path'];if($tag-notin@('MY-FILES','MY-FILES-FAST')){Resp $s 400 'application/json' '{"ok":false,"message":"bad storage"}';return};$size=0L;[void][int64]::TryParse($r.Headers['content-length'],[ref]$size);if($size-le0){Resp $s 400 'application/json' '{"ok":false,"message":"empty file"}';return};if($size-gt2147483648){Resp $s 413 'application/json' '{"ok":false,"message":"file too large"}';return};if([string]::IsNullOrWhiteSpace($rel)){$rel=U $r.Headers['x-filename']};$id=[guid]::NewGuid().ToString('N');$dir=Join-Path $JobsDir $id;New-Item-ItemType Directory-Force-Path$dir|Out-Null;$src=Join-Path $dir 'source.bin';$out=[IO.File]::Open($src,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None);try{$left=$size;$buf=New-Object byte[] 1048576;while($left-gt0){$n=$s.Read($buf,0,[int][math]::Min($buf.Length,$left));if($n-le0){throw 'client disconnected'};$out.Write($buf,0,$n);$left-=$n}}finally{$out.Dispose()};$jp=Join-Path $JobsDir ($id+'.json');$job=@{id=$id;sourcePath=$src;assetName=(Enc $rel);tag=$tag;token=$token;relativePath=$rel;size=$size;startedAt=(Get-Date).ToString('o')};State $jp $job;State (Join-Path $JobsDir ($id+'.status.json')) @{ok=$true;state='queued';phase='QUEUED';message='Received from browser';size=$size;sent=$size;percent=0;startedAt=$job.startedAt};Start-Process -FilePath 'powershell.exe' -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File "'+$ScriptPath+'" -Worker -JobFile "'+$jp+'"') -WindowStyle Hidden|Out-Null;Resp $s 201 'application/json' (@{ok=$true;id=$id}|ConvertTo-Json -Compress);return};Resp $s 404 'application/json' '{"ok":false,"message":"not found"}'}
$listener=New-Object Net.Sockets.TcpListener([Net.IPAddress]::Parse('127.0.0.1'),$Port);$listener.Start();Write-Host 'F file bridge running on http://127.0.0.1:8765';while($true){$c=$listener.AcceptTcpClient();try{Handle $c}catch{try{Resp $c.GetStream() 500 'application/json' (@{ok=$false;message=$_.Exception.Message}|ConvertTo-Json -Compress)}catch{}}finally{$c.Close()}}
