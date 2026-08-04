[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
if ($env:OS -ne 'Windows_NT') { throw 'Windows packaging must run on Windows.' }

# Keep every Python child process UTF-8 encoded on Windows, including pytest
# subprocesses and the standalone CLI regressions.
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

function Invoke-Checked([string]$File, [string[]]$Arguments) {
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $File $Arguments" }
}

function Find-IsccExecutable {
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command -and (Test-Path -LiteralPath $command.Source)) { return $command.Source }

    $candidates = @(
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        'C:\Program Files\Inno Setup 6\ISCC.exe'
    )
    if ($env:LOCALAPPDATA) { $candidates += (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe') }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }

    $uninstallRoots = @(
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKCU:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )
    foreach ($entry in Get-ItemProperty -Path $uninstallRoots -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -match '^Inno Setup' }) {
        if ($entry.InstallLocation) {
            $candidate = Join-Path $entry.InstallLocation 'ISCC.exe'
            if (Test-Path -LiteralPath $candidate) { return $candidate }
        }
    }
    return $null
}

$pyLauncher = Get-Command py -ErrorAction SilentlyContinue
if (-not $pyLauncher) { throw 'Python 3.11 is required, but the Windows py launcher is unavailable. Install Python 3.11, then rerun packaging/build_windows.ps1.' }
$pythonExe = (& $pyLauncher.Source -3.11 -c "import sys; print(sys.executable)" 2>$null).Trim()
if (-not $pythonExe) { throw 'Python 3.11 is required. Install Python 3.11, then rerun packaging/build_windows.ps1.' }
$version = (& $pythonExe -c "from app_version import VERSION; print(VERSION)").Trim()
$appName = (& $pythonExe -c "from app_version import APP_NAME; print(APP_NAME)").Trim()
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
Invoke-Checked $buildPython @('scripts\smoke_frozen_creator_ui.py')
& (Join-Path $PSScriptRoot 'package_portable.ps1') -DistRoot $distDir -OutputRoot $releaseDir -Version $version -AppName $appName | Out-Host

$iscc = Find-IsccExecutable
if (-not $iscc) { throw 'Inno Setup 6 compiler (ISCC.exe) was not found. Installer is required for this release build.' }
Write-Output "Using Inno Setup compiler: $iscc"
$installerStage = Join-Path $releaseDir 'installer-stage'
New-Item -ItemType Directory -Force -Path $installerStage | Out-Null
$installerSource = Join-Path $distDir $appName
Get-ChildItem -LiteralPath $installerSource -Force | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $installerStage -Recurse -Force }
Invoke-Checked $iscc @("/DMyAppVersion=$version", "/DMyAppName=$appName", 'packaging\installer.iss')
$installerBuilt = $true

$portable = Join-Path $releaseDir "AI-Video-Production-Verifier-Portable-v$version.zip"
$setup = Join-Path $releaseDir "AI-Video-Production-Verifier-Setup-v$version.exe"
$artifacts = @($portable) + $(if (Test-Path -LiteralPath $setup) { @($setup) } else { @() })
$scan = & $buildPython -c "from pathlib import Path; from build_support.release_utils import scan_tree,scan_zip; import sys; paths=[Path(r'$distDir'),Path(r'$portable')]; findings=scan_tree(paths[0])+scan_zip(paths[1]); print('\\n'.join(findings)); sys.exit(bool(findings))"
if ($LASTEXITCODE -ne 0) { throw "Sensitive information scan failed:`n$scan" }
Write-Output 'SCAN_RESULT = OK'
$commit = (& git rev-parse HEAD).Trim(); $pythonVersion = (& $buildPython --version).Trim(); $pyinstallerVersion = (& $buildPython -m PyInstaller --version).Trim()
$metadataArgs = @(
    'build_support\generate_release_metadata.py',
    '--release-dir', $releaseDir,
    '--version', $version,
    '--commit', $commit,
    '--python-version', $pythonVersion,
    '--pyinstaller-version', $pyinstallerVersion,
    '--portable-built'
)
if ($installerBuilt) { $metadataArgs += '--installer-built' }
foreach ($artifact in $artifacts) { $metadataArgs += @('--artifact', [string]$artifact) }
Invoke-Checked $buildPython $metadataArgs
Get-ChildItem -LiteralPath $releaseDir -File | ForEach-Object { "ARTIFACT: $($_.FullName) SHA256=$((Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash)" }
