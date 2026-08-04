[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$FrozenAppDir,[Parameter(Mandatory=$true)][string]$FrozenExe,[Parameter(Mandatory=$true)][string]$OutputRoot,[Parameter(Mandatory=$true)][string]$Version)
$ErrorActionPreference='Stop'; $folderName="AI-Video-Production-Verifier-Portable-v$Version"; $source=(Resolve-Path -LiteralPath $FrozenAppDir).Path; $exe=(Resolve-Path -LiteralPath $FrozenExe).Path
if((Split-Path -Parent $exe) -ne $source){throw "Frozen executable is not in the supplied app directory: $exe"}; $exeName=Split-Path -Leaf $exe
$portableRoot=Join-Path $OutputRoot $folderName; Remove-Item -LiteralPath $portableRoot -Recurse -Force -ErrorAction SilentlyContinue; New-Item -ItemType Directory -Force -Path $portableRoot|Out-Null
Get-ChildItem -LiteralPath $source -Force | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $portableRoot -Recurse -Force }; Copy-Item -LiteralPath (Join-Path $PSScriptRoot '..\LICENSE') -Destination $portableRoot -Force
@"
AI Video Production Verifier v$Version - Quick Start
1. No Python installation is required. Extract this ZIP completely before running.
2. Double-click $exeName.
3. On first use, enter your own DeepSeek API Key. It is stored in Windows Credential Manager.
4. Professional JSON local-rule mode works without an API Key.
5. Natural-language analysis and semantic auditing require your configured DeepSeek API Key.
6. The application contains no API Key and does not upload telemetry.
"@ | Set-Content -LiteralPath (Join-Path $portableRoot 'README-Quick-Start.txt') -Encoding utf8
$zipPath=Join-Path $OutputRoot "$folderName.zip"; Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue; Compress-Archive -LiteralPath $portableRoot -DestinationPath $zipPath -Force; Write-Output $zipPath
