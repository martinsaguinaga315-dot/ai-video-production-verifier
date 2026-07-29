[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$DistRoot,[Parameter(Mandatory=$true)][string]$OutputRoot,[Parameter(Mandatory=$true)][string]$Version,[Parameter(Mandatory=$true)][string]$AppName)
$ErrorActionPreference='Stop'; $folderName="AI-Video-Production-Verifier-Portable-v$Version"; $source=Join-Path $DistRoot $AppName
if(-not(Test-Path -LiteralPath (Join-Path $source "$AppName.exe"))){throw "Missing onedir application: $source"}
$portableRoot=Join-Path $OutputRoot $folderName; Remove-Item -LiteralPath $portableRoot -Recurse -Force -ErrorAction SilentlyContinue; New-Item -ItemType Directory -Force -Path $portableRoot|Out-Null
Copy-Item -LiteralPath (Join-Path $source '*') -Destination $portableRoot -Recurse -Force; Copy-Item -LiteralPath (Join-Path $PSScriptRoot '..\LICENSE') -Destination $portableRoot -Force
@"
AI Video Production Verifier v$Version - Quick Start
1. No Python installation is required. Extract this ZIP completely before running.
2. Double-click $AppName.exe.
3. On first use, enter your own DeepSeek API Key. It is stored in Windows Credential Manager.
4. Professional JSON local-rule mode works without an API Key.
5. Natural-language analysis and semantic auditing require your configured DeepSeek API Key.
6. The application contains no API Key and does not upload telemetry.
"@ | Set-Content -LiteralPath (Join-Path $portableRoot 'README-Quick-Start.txt') -Encoding utf8
$zipPath=Join-Path $OutputRoot "$folderName.zip"; Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue; Compress-Archive -LiteralPath $portableRoot -DestinationPath $zipPath -Force; Write-Output $zipPath
