[CmdletBinding()]
param([switch]$SkipInstaller)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
if ($env:OS -ne 'Windows_NT') { throw 'Windows packaging must run on Windows.' }

function Invoke-Checked([string]$File, [string[]]$Arguments) {
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $File $Arguments" }
}

$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if (-not $pyLauncher) { throw 'Python 3.11 is required, but the Windows py launcher is unavailable. Install Python 3.11, then rerun packaging/build_windows.ps1.' }
$pythonExe = (& $pyLauncher.Source -3.11 -c "import sys; print(sys.executable)" 2>$null).Trim()
if (-not $pythonExe) { throw 'Python 3.11 is required. Install Python 3.11, then rerun packaging/build_windows.ps1.' }
$previousPythonIoEncoding = $env:PYTHONIOENCODING
try {
    # The hosted Windows runner can default Python stdout to cp1252.  APP_NAME
    # contains Chinese characters, so read build metadata through UTF-8.
    $env:PYTHONIOENCODING = 'utf-8'
    $version = (& $pythonExe -c "from app_version import VERSION; print(VERSION)").Trim()
    $appName = (& $pythonExe -c "from app_version import APP_NAME; print(APP_NAME)").Trim()
}
finally {
    $env:PYTHONIOENCODING = $previousPythonIoEncoding
}
if ([string]::IsNullOrWhiteSpace($appName)) { throw 'Application name metadata was empty.' }
$venv = Join-Path $root '.build-venv'
$buildDir, $distDir, $releaseDir = (Join-Path $root 'build'), (Join-Path $root 'dist'), (Join-Path $root 'release')
foreach ($path in @($venv, $buildDir, $distDir, $releaseDir)) { if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force } }

Invoke-Checked $pythonExe @('-m', 'venv', $venv)
$buildPython = Join-Path $venv 'Scripts\python.exe'
Invoke-Checked $buildPython @('-m', 'pip', 'install', '--upgrade', 'pip')
Invoke-Checked $buildPython @('-m', 'pip', 'install', '-r', 'requirements-dev.txt')
Invoke-Checked $buildPython @('-m', 'py_compile', 'desktop_app.py', 'verify.py', 'app_version.py')
Invoke-Checked $buildPython @('-m', 'pytest', '-q')
Invoke-Checked $buildPython @('verify.py', 'examples\clean\facts.json', 'examples\clean\director_output.json', '--compact')
& $buildPython verify.py examples\unknown_character_error\facts.json examples\unknown_character_error\director_output.json --compact
if ($LASTEXITCODE -ne 1) { throw "Unknown-character CLI regression returned $LASTEXITCODE, expected 1." }
Invoke-Checked $buildPython @('-m', 'PyInstaller', '--noconfirm', '--clean', 'packaging\windows.spec')
& (Join-Path $PSScriptRoot 'verify_build.ps1') -DistRoot $distDir -AppName $appName
& (Join-Path $PSScriptRoot 'package_portable.ps1') -DistRoot $distDir -OutputRoot $releaseDir -Version $version -AppName $appName | Out-Host

$installerBuilt = $false
if (-not $SkipInstaller) {
    $iscc = @('C:\Program Files (x86)\Inno Setup 6\ISCC.exe', 'C:\Program Files\Inno Setup 6\ISCC.exe') | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if ($iscc) {
        $installerStage = Join-Path $releaseDir 'installer-stage'
        New-Item -ItemType Directory -Force -Path $installerStage | Out-Null
        Copy-Item -LiteralPath (Join-Path $distDir "$appName\*") -Destination $installerStage -Recurse -Force
        Invoke-Checked $iscc @("/DMyAppVersion=$version", "/DMyAppName=$appName", 'packaging\installer.iss'); $installerBuilt = $true
    }
    else { Write-Warning 'Inno Setup 6 was not found. Portable build completed; installer was not generated.' }
}

$portable = Join-Path $releaseDir "AI-Video-Production-Verifier-Portable-v$version.zip"
$setup = Join-Path $releaseDir "AI-Video-Production-Verifier-Setup-v$version.exe"
$artifacts = @($portable) + $(if (Test-Path -LiteralPath $setup) { @($setup) } else { @() })
$scan = & $buildPython -c "from pathlib import Path; from build_support.release_utils import scan_tree,scan_zip; import sys; paths=[Path(r'$distDir'),Path(r'$portable')]; findings=scan_tree(paths[0])+scan_zip(paths[1]); print('\\n'.join(findings)); sys.exit(bool(findings))"
if ($LASTEXITCODE -ne 0) { throw "Sensitive information scan failed:`n$scan" }
Write-Output 'SCAN_RESULT = OK'
$commit = (& git rev-parse HEAD).Trim(); $pythonVersion = (& $buildPython --version).Trim(); $pyinstallerVersion = (& $buildPython -m PyInstaller --version).Trim()
& $buildPython -c "from pathlib import Path; from build_support.release_utils import write_manifest,write_sha256s; items=[Path(r'$p') for p in r'$($artifacts -join '|')'.split('|') if p]; root=Path(r'$releaseDir'); write_sha256s(items,root/'SHA256SUMS.txt'); write_manifest(root/'release_manifest_v$version.json',commit=r'$commit',python_version=r'$pythonVersion',pyinstaller_version=r'$pyinstallerVersion',test_result='pytest passed',artifacts=items,smoke_passed=True,scan_passed=True,installer_built=$($installerBuilt.ToString().ToLower()),portable_built=True)"
Get-ChildItem -LiteralPath $releaseDir -File | ForEach-Object { "ARTIFACT: $($_.FullName) SHA256=$((Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash)" }
