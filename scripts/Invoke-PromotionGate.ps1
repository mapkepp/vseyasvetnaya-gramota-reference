[CmdletBinding()]
param(
 [Parameter(Mandatory)][string]$RepositoryPath,
 [Parameter(Mandatory)][string]$DevRef,
 [Parameter(Mandatory)][string]$ProductionRef,
 [switch]$CreateBackupSnapshot
)
$ErrorActionPreference="Stop"
if(-not(Test-Path $RepositoryPath)){throw "RepositoryPath not found"}
if(-not(Get-Command git -ErrorAction SilentlyContinue)){throw "git not found"}
Push-Location $RepositoryPath
try {
 $status=& git status --porcelain
 if($status){throw "Working tree is not clean"}
 $dev=& git rev-parse $DevRef
 $prod=& git rev-parse $ProductionRef
 if(-not $dev -or -not $prod){throw "Cannot resolve refs"}
 if($CreateBackupSnapshot){
   $stamp=(Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
   $backup="backup/$stamp"
   & git branch $backup $prod
   if($LASTEXITCODE -ne 0){throw "Backup snapshot creation failed"}
 }
 [pscustomobject]@{
   status="PASS";evidence="MEASURED";development_sha=$dev;production_sha=$prod;
   backup_created=[bool]$CreateBackupSnapshot;verified_at=(Get-Date).ToUniversalTime().ToString("o")
 }
} finally {Pop-Location}
