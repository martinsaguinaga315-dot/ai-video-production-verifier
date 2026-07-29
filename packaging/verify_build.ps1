[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$DistRoot,[Parameter(Mandatory=$true)][string]$AppName)
$ErrorActionPreference='Stop'; $exe=Join-Path $DistRoot "$AppName\$AppName.exe"
if(-not(Test-Path -LiteralPath $exe)){throw "Missing frozen executable: $exe"}; if(-not(Test-Path -LiteralPath (Join-Path $DistRoot "$AppName\_internal"))){throw 'Missing bundled runtime: _internal'}; foreach($required in @('examples','LICENSE')){if(-not(Test-Path -LiteralPath (Join-Path $DistRoot "$AppName\_internal\$required"))){throw "Missing bundled resource: $required"}}
$oldSmoke=$env:AIVPV_SMOKE_TEST; try{$env:AIVPV_SMOKE_TEST='1'; $process=Start-Process -FilePath $exe -WorkingDirectory (Split-Path $exe) -WindowStyle Hidden -PassThru; Start-Sleep -Seconds 5; if($process.HasExited){throw "Frozen EXE exited early with code $($process.ExitCode)"}; Stop-Process -Id $process.Id -Force} finally {$env:AIVPV_SMOKE_TEST=$oldSmoke}; Write-Output 'EXE_SMOKE_RESULT = OK'
