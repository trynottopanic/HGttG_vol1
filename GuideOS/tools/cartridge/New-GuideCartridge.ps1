[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $Source,
    [Parameter(Mandatory = $true)] [string] $Id,
    [Parameter(Mandatory = $true)] [string] $Name,
    [string] $Version = '1.0.0',
    [ValidateSet('data', 'media', 'recipe', 'application', 'adapter')]
    [string] $Kind = 'data',
    [string] $Summary = '',
    [string[]] $Capability = @(),
    [ValidateSet('', 'feature.wifi.rg35xxh', 'feature.developer-link.rg35xxh',
                 'application.wikipedia.rg35xxh')]
    [string] $InstallAction = '',
    [Parameter(Mandatory = $true)] [string] $Output,
    [switch] $Force
)

. (Join-Path $PSScriptRoot 'GuideCartridge.Common.ps1')
Import-GuideCompressionAssemblies

Assert-GuideIdentifier -Id $Id
Assert-GuideVersion -Version $Version
if ($Name.Length -lt 1 -or $Name.Length -gt 64 -or $Name -match '[\x00-\x1f]') {
    throw 'Name must contain 1-64 characters.'
}
if ($Summary.Length -gt 200 -or $Summary -match '[\x00-\x1f]') {
    throw 'Summary must contain no more than 200 characters.'
}
foreach ($requestedCapability in $Capability) {
    if ($requestedCapability -notmatch '^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+$') {
        throw "Invalid capability name: $requestedCapability"
    }
}

$sourcePath = (Resolve-Path -LiteralPath $Source).Path
if (-not (Test-Path -LiteralPath $sourcePath -PathType Container)) {
    throw "Source is not a folder: $Source"
}
$sourcePrefix = $sourcePath.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
$outputPath = [System.IO.Path]::GetFullPath($Output)
if (-not [string]::Equals([System.IO.Path]::GetExtension($outputPath), '.guide', [System.StringComparison]::OrdinalIgnoreCase)) {
    $outputPath += '.guide'
}
if ($outputPath.StartsWith($sourcePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Save the finished cartridge outside its source folder.'
}
$outputFolder = Split-Path -Parent $outputPath
if (-not $outputFolder) { $outputFolder = (Get-Location).Path }
[System.IO.Directory]::CreateDirectory($outputFolder) | Out-Null
if ((Test-Path -LiteralPath $outputPath) -and -not $Force) {
    throw "Output already exists. Use -Force to replace it: $outputPath"
}

$sourceItems = @(Get-ChildItem -LiteralPath $sourcePath -Recurse -Force)
foreach ($item in $sourceItems) {
    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Links and filesystem redirections are not allowed: $($item.FullName)"
    }
}
$files = @($sourceItems | Where-Object { -not $_.PSIsContainer } | Sort-Object FullName)
if ($files.Count -gt 4096) {
    throw 'A cartridge may contain at most 4096 files.'
}

$inventory = @()
foreach ($file in $files) {
    $relative = $file.FullName.Substring($sourcePrefix.Length).Replace('\', '/')
    $entryPath = "CONTENT/$relative"
    Assert-GuideEntryPath -Path $entryPath
    $inventory += [pscustomobject][ordered]@{
        path = $entryPath
        bytes = [int64]$file.Length
        sha256 = Get-GuideSha256FromFile -Path $file.FullName
    }
}

$manifest = [ordered]@{
    format = 'GUIDE-CARTRIDGE-1'
    id = $Id
    name = $Name
    version = $Version
    kind = $Kind
    summary = $Summary
    capabilities = @($Capability | Sort-Object -Unique)
    installAction = $(if ($InstallAction) { $InstallAction } else { $null })
    entrypoint = $null
    files = $inventory
}
$json = $manifest | ConvertTo-Json -Depth 8
$utf8 = New-Object System.Text.UTF8Encoding($false)
$manifestBytes = $utf8.GetBytes($json + "`n")
if ($manifestBytes.Length -gt 262144) {
    throw 'The generated manifest exceeds the 256 KiB safety limit.'
}

$temporaryPath = Join-Path $outputFolder ('.' + [System.IO.Path]::GetFileName($outputPath) + '.' + [guid]::NewGuid().ToString('N') + '.partial')
try {
    $archive = [System.IO.Compression.ZipFile]::Open($temporaryPath, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        $manifestEntry = $archive.CreateEntry('GUIDE/manifest.json', [System.IO.Compression.CompressionLevel]::Optimal)
        $manifestEntry.LastWriteTime = [datetimeoffset]'2000-01-01T00:00:00Z'
        $manifestStream = $manifestEntry.Open()
        try { $manifestStream.Write($manifestBytes, 0, $manifestBytes.Length) }
        finally { $manifestStream.Dispose() }

        for ($index = 0; $index -lt $files.Count; $index++) {
            $compression = Get-GuideCompressionLevel -Path $files[$index].FullName
            $entry = $archive.CreateEntry($inventory[$index].path, $compression)
            $entry.LastWriteTime = [datetimeoffset]'2000-01-01T00:00:00Z'
            $input = [System.IO.File]::OpenRead($files[$index].FullName)
            $outputStream = $entry.Open()
            try { $input.CopyTo($outputStream) }
            finally {
                $outputStream.Dispose()
                $input.Dispose()
            }
        }
    }
    finally { $archive.Dispose() }

    & (Join-Path $PSScriptRoot 'Test-GuideCartridge.ps1') -Path $temporaryPath -Quiet | Out-Null
    if (Test-Path -LiteralPath $outputPath) { Remove-Item -LiteralPath $outputPath -Force }
    Move-Item -LiteralPath $temporaryPath -Destination $outputPath
    $packageHash = Get-GuideSha256FromFile -Path $outputPath
    [System.IO.File]::WriteAllText($outputPath + '.sha256', "$packageHash  $([System.IO.Path]::GetFileName($outputPath))`n", $utf8)
}
finally {
    if (Test-Path -LiteralPath $temporaryPath) { Remove-Item -LiteralPath $temporaryPath -Force }
}

Write-Host ''
Write-Host 'CARTRIDGE READY' -ForegroundColor Green
Write-Host "Name:    $Name"
Write-Host "Package: $outputPath"
Write-Host "Files:   $($files.Count)"
Write-Host "SHA-256: $packageHash"
