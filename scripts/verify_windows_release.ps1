[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ReleaseDirectory,
    [string]$ExpectedVersion,
    [Parameter(Mandatory = $true)][string]$ExpectedCommit,
    [string]$HistoryDirectory,
    [string]$InstalledExecutable,
    [switch]$SkipHistoryCheck,
    [switch]$SkipInstalledAppCheck,
    [switch]$LaunchInstalledApp
)

$ErrorActionPreference = "Stop"

function Get-ProjectVersion {
    $versionFile = Join-Path $PSScriptRoot "..\app_version.py"
    $content = Get-Content -LiteralPath $versionFile -Raw -Encoding UTF8
    $match = [regex]::Match($content, '(?m)^VERSION\s*=\s*["'']([^"'']+)["'']')
    if (-not $match.Success -or [string]::IsNullOrWhiteSpace($match.Groups[1].Value)) {
        throw "Could not read a non-empty VERSION from $versionFile"
    }
    return $match.Groups[1].Value
}

function Assert-NonEmptyFile([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label is missing: $Path" }
    if ((Get-Item -LiteralPath $Path).Length -le 0) { throw "$Label is empty: $Path" }
}

function Normalize-ReleaseVersion([string]$Value) {
    $match = [regex]::Match($Value, '\d+(?:\.\d+){1,3}')
    if (-not $match.Success) { return $null }
    return ($match.Value -replace '(?:\.0)+$', '')
}

function Get-ExpectedSha256([string]$ChecksumFile, [string]$FileName) {
    $line = Get-Content -LiteralPath $ChecksumFile -Encoding UTF8 | Where-Object {
        $_ -match ('^([A-Fa-f0-9]{64})\s+\*?' + [regex]::Escape($FileName) + '$')
    } | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($line)) { throw "SHA256SUMS.txt has no checksum for $FileName" }
    return ([regex]::Match($line, '^[A-Fa-f0-9]{64}')).Value.ToLowerInvariant()
}

function Test-PortableZip([string]$ZipPath) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = $null
    try {
        $archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
        if ($archive.Entries.Count -eq 0) { throw "Portable ZIP contains no files" }
        $names = @($archive.Entries | ForEach-Object { $_.FullName })
        $portableExeName = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('QUnop4bpopHliLbkvZzmoLjpqozlmaguZXhl'))
        if (-not ($names | Where-Object { $_ -match ('(^|/)' + [regex]::Escape($portableExeName) + '$') })) { throw "Portable ZIP does not contain the application executable" }
        if (-not ($names | Where-Object { $_ -match '(^|/)_internal/' })) { throw "Portable ZIP does not contain _internal directory content" }
    } finally {
        if ($null -ne $archive) { $archive.Dispose() }
    }
}

function Find-NonEmptyApiKeyField($Value) {
    if ($null -eq $Value) { return $false }
    if ($Value -is [System.Collections.IDictionary]) {
        foreach ($key in $Value.Keys) {
            if ($key -in @('api_key', 'api-key', 'apiKey') -and -not [string]::IsNullOrWhiteSpace([string]$Value[$key])) { return $true }
            if (Find-NonEmptyApiKeyField $Value[$key]) { return $true }
        }
    } elseif ($Value -is [System.Collections.IEnumerable] -and -not ($Value -is [string])) {
        foreach ($item in $Value) { if (Find-NonEmptyApiKeyField $item) { return $true } }
    } elseif ($Value -is [psobject]) {
        foreach ($property in $Value.PSObject.Properties) {
            if ($property.Name -in @('api_key', 'api-key', 'apiKey') -and -not [string]::IsNullOrWhiteSpace([string]$property.Value)) { return $true }
            if (Find-NonEmptyApiKeyField $property.Value) { return $true }
        }
    }
    return $false
}

function Test-HistoryDirectory([string]$Directory) {
    if (-not (Test-Path -LiteralPath $Directory -PathType Container)) { throw "History directory does not exist: $Directory" }
    $records = @(Get-ChildItem -LiteralPath $Directory -Filter '*.json' -File)
    if ($records.Count -eq 0) { Write-Output ([System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('5rKh5pyJ5Y6G5Y+y6K6w5b2V5Y+v6aqM6K+B'))); return }
    foreach ($record in $records) {
        $raw = Get-Content -LiteralPath $record.FullName -Raw -Encoding UTF8
        try { $history = $raw | ConvertFrom-Json } catch { throw "History JSON is invalid: $($record.Name)" }
        foreach ($field in @('history_id', 'created_at', 'idea', 'result')) {
            if ($null -eq $history.PSObject.Properties[$field] -or [string]::IsNullOrWhiteSpace([string]$history.$field)) { throw "History JSON is missing or empty '$field': $($record.Name)" }
        }
        if ($null -eq $history.result.PSObject.Properties['status'] -or [string]::IsNullOrWhiteSpace([string]$history.result.status)) { throw "History JSON result.status is missing or empty: $($record.Name)" }
        if ($raw -match 'sk-[A-Za-z0-9_-]{12,}' -or (Find-NonEmptyApiKeyField $history)) { throw "Possible API key found in history record: $($record.Name)" }
    }
    Write-Output "History records verified: $($records.Count)"
}

function Invoke-ReleaseAcceptance {
    if ([string]::IsNullOrWhiteSpace($ExpectedVersion)) { $ExpectedVersion = Get-ProjectVersion }
    if ([string]::IsNullOrWhiteSpace($ExpectedCommit)) { throw "ExpectedCommit must not be empty" }
    $release = (Resolve-Path -LiteralPath $ReleaseDirectory -ErrorAction Stop).Path
    $setupName = "AI-Video-Production-Verifier-Setup-v$ExpectedVersion.exe"
    $portableName = "AI-Video-Production-Verifier-Portable-v$ExpectedVersion.zip"
    $setup = Join-Path $release $setupName; $portable = Join-Path $release $portableName
    $checksums = Join-Path $release 'SHA256SUMS.txt'; $manifestPath = Join-Path $release "release_manifest_v$ExpectedVersion.json"
    Assert-NonEmptyFile $setup 'Setup asset'; Assert-NonEmptyFile $portable 'Portable asset'; Assert-NonEmptyFile $checksums 'SHA256SUMS.txt'; Assert-NonEmptyFile $manifestPath 'Release manifest'
    $manifest = (Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8) | ConvertFrom-Json
    foreach ($field in @('git_commit', 'version')) { if ($null -eq $manifest.PSObject.Properties[$field] -or [string]::IsNullOrWhiteSpace([string]$manifest.$field)) { throw "Manifest field is missing or empty: $field" } }
    if ($manifest.git_commit -ne $ExpectedCommit) { throw "Manifest git_commit does not match ExpectedCommit" }
    if ($manifest.version -ne $ExpectedVersion) { throw "Manifest version does not match ExpectedVersion" }
    Write-Output 'Manifest verification passed'
    foreach ($asset in @(@($setup, $setupName), @($portable, $portableName))) {
        $expected = Get-ExpectedSha256 $checksums $asset[1]; $actual = (Get-FileHash -LiteralPath $asset[0] -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $expected) { throw "SHA256 mismatch for $($asset[1])" }
    }
    Write-Output 'SHA256 verification passed for Setup and Portable assets'
    Test-PortableZip $portable
    Write-Output 'Portable ZIP structure verification passed'
    if (-not $SkipHistoryCheck) { if ([string]::IsNullOrWhiteSpace($HistoryDirectory)) { $HistoryDirectory = Join-Path $env:LOCALAPPDATA 'AIVideoProductionVerifier\creator_history' }; Test-HistoryDirectory $HistoryDirectory }
    if (-not $SkipInstalledAppCheck -and -not [string]::IsNullOrWhiteSpace($InstalledExecutable)) {
        Assert-NonEmptyFile $InstalledExecutable 'Installed executable'
        $versionInfo = (Get-Item -LiteralPath $InstalledExecutable).VersionInfo
        $installedVersion = $versionInfo.FileVersion
        if ([string]::IsNullOrWhiteSpace($installedVersion)) { $installedVersion = $versionInfo.ProductVersion }
        if ([string]::IsNullOrWhiteSpace($installedVersion)) {
            Write-Output 'Installed executable has no readable FileVersion or ProductVersion; continuing with existence check only'
        } else {
            $normalizedInstalled = Normalize-ReleaseVersion $installedVersion
            $normalizedExpected = Normalize-ReleaseVersion $ExpectedVersion
            if ($null -ne $normalizedInstalled -and $null -ne $normalizedExpected -and $normalizedInstalled -ne $normalizedExpected) { throw "Installed executable version $installedVersion does not match ExpectedVersion $ExpectedVersion" }
            Write-Output "Installed executable version information: $installedVersion"
        }
        if ($LaunchInstalledApp) { Start-Process -FilePath $InstalledExecutable }
    }
    Write-Output 'RELEASE_ACCEPTANCE_RESULT = OK'
}

try { Invoke-ReleaseAcceptance; exit 0 } catch { Write-Error "RELEASE_ACCEPTANCE_RESULT = FAILED: $($_.Exception.Message)"; exit 1 }
