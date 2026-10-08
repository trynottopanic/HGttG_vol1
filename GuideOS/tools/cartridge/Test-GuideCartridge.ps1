[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $Path,
    [switch] $Quiet,
    [switch] $PassThru
)

. (Join-Path $PSScriptRoot 'GuideCartridge.Common.ps1')
Import-GuideCompressionAssemblies

$packagePath = (Resolve-Path -LiteralPath $Path).Path
$archive = [System.IO.Compression.ZipFile]::OpenRead($packagePath)
try {
    if ($archive.Entries.Count -gt 4097) { throw 'Cartridge contains too many entries.' }
    $names = @{}
    $entries = @{}
    [int64]$totalBytes = 0
    foreach ($entry in $archive.Entries) {
        Assert-GuideEntryPath -Path $entry.FullName
        if ($entry.FullName.EndsWith('/')) { throw "Directory entries are not permitted: $($entry.FullName)" }
        $key = $entry.FullName.ToLowerInvariant()
        if ($names.ContainsKey($key)) { throw "Duplicate cartridge path: $($entry.FullName)" }
        $names[$key] = $true
        $entries[$entry.FullName] = $entry
        $totalBytes += [int64]$entry.Length
        if ($totalBytes -gt 137438953472) { throw 'Expanded cartridge size exceeds 128 GiB.' }
    }

    if (-not $entries.ContainsKey('GUIDE/manifest.json')) { throw 'GUIDE/manifest.json is missing.' }
    $manifestEntry = $entries['GUIDE/manifest.json']
    if ($manifestEntry.Length -gt 262144) { throw 'Manifest exceeds 256 KiB.' }
    $reader = New-Object System.IO.StreamReader($manifestEntry.Open(), (New-Object System.Text.UTF8Encoding($false, $true)))
    try { $manifest = ($reader.ReadToEnd() | ConvertFrom-Json) }
    finally { $reader.Dispose() }

    if ($manifest.installAction -eq 'application.install.v0') {
        $python = (Get-Command python -ErrorAction Stop).Source
        $verifier = Join-Path $PSScriptRoot '../../package/guide-installer/guide_cartridge.py'
        $raw = & $python -X utf8 $verifier $packagePath
        if ($LASTEXITCODE -ne 0) { throw 'Application cartridge validation failed.' }
        $verified = ($raw | ConvertFrom-Json)
        if ($PassThru) {
            [pscustomobject]@{ Path=$packagePath; Id=$verified.manifest.id; Name=$verified.manifest.name; Version=$verified.manifest.version; Kind='application'; Summary=$verified.manifest.summary; Capabilities=@($verified.manifest.capabilities); InstallAction='application.install.v0'; FileCount=@($verified.manifest.files).Count; ExpandedBytes=$verified.expandedBytes; Sha256=$verified.sha256 }
        } elseif (-not $Quiet) { Write-Host 'Unsigned application cartridge verified.' }
        return
    }
    if ($manifest.format -ne 'GUIDE-CARTRIDGE-1') { throw 'Unsupported cartridge format.' }
    Assert-GuideIdentifier -Id ([string]$manifest.id)
    Assert-GuideVersion -Version ([string]$manifest.version)
    if ([string]::IsNullOrWhiteSpace([string]$manifest.name) -or
        ([string]$manifest.name).Length -gt 64 -or
        [string]$manifest.name -match '[\x00-\x1f]') {
        throw 'Manifest name is missing or too long.'
    }
    if (([string]$manifest.summary).Length -gt 200 -or [string]$manifest.summary -match '[\x00-\x1f]') {
        throw 'Manifest summary is too long or contains control characters.'
    }
    if (@('data', 'media', 'recipe', 'application', 'adapter') -notcontains [string]$manifest.kind) {
        throw 'Manifest kind is not recognized.'
    }
    if ($null -ne $manifest.entrypoint) { throw 'Format 1 entrypoint must be null.' }
    foreach ($requestedCapability in @($manifest.capabilities)) {
        if ([string]$requestedCapability -notmatch '^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+$') {
            throw "Invalid capability name: $requestedCapability"
        }
    }
    $installAction = $null
    if ($manifest.PSObject.Properties['installAction']) {
        $installAction = $manifest.installAction
    }
    if ($null -ne $installAction -and
        @('feature.wifi.rg35xxh', 'feature.developer-link.rg35xxh',
          'application.wikipedia.rg35xxh',
          'application.semiotic-engine.rg35xxh',
          'application.emulation.rg35xxh') -notcontains [string]$installAction) {
        throw "Unsupported installation action: $installAction"
    }

    $declared = @{}
    foreach ($file in @($manifest.files)) {
        $contentPath = [string]$file.path
        Assert-GuideEntryPath -Path $contentPath
        if (-not $contentPath.StartsWith('CONTENT/')) { throw "Content path is outside CONTENT/: $contentPath" }
        if ($declared.ContainsKey($contentPath)) { throw "Manifest declares a file twice: $contentPath" }
        if (-not $entries.ContainsKey($contentPath)) { throw "Declared content is missing: $contentPath" }
        $contentEntry = $entries[$contentPath]
        if ([int64]$file.bytes -lt 0 -or [int64]$file.bytes -ne [int64]$contentEntry.Length) {
            throw "Wrong byte count: $contentPath"
        }
        if ([string]$file.sha256 -notmatch '^[0-9a-fA-F]{64}$') { throw "Invalid SHA-256: $contentPath" }
        $stream = $contentEntry.Open()
        try { $actualHash = Get-GuideSha256FromStream -Stream $stream }
        finally { $stream.Dispose() }
        if ($actualHash -ne ([string]$file.sha256).ToLowerInvariant()) { throw "Hash mismatch: $contentPath" }
        $declared[$contentPath] = $true
    }
    foreach ($entryName in $entries.Keys) {
        if ($entryName -ne 'GUIDE/manifest.json' -and -not $declared.ContainsKey($entryName)) {
            throw "Undeclared file in cartridge: $entryName"
        }
    }

    $result = [pscustomobject]@{
        Path = $packagePath
        Id = [string]$manifest.id
        Name = [string]$manifest.name
        Version = [string]$manifest.version
        Kind = [string]$manifest.kind
        Summary = [string]$manifest.summary
        Capabilities = @($manifest.capabilities)
        InstallAction = $(if ($null -ne $installAction) { [string]$installAction } else { '' })
        FileCount = $declared.Count
        ExpandedBytes = $totalBytes - [int64]$manifestEntry.Length
        Sha256 = Get-GuideSha256FromFile -Path $packagePath
    }
    if (-not $Quiet) {
        Write-Host ''
        Write-Host 'CARTRIDGE VERIFIED' -ForegroundColor Green
        Write-Host "Name:    $($result.Name)"
        Write-Host "ID:      $($result.Id)"
        Write-Host "Version: $($result.Version)"
        Write-Host "Kind:    $($result.Kind)"
        if ($result.InstallAction) { Write-Host "Action:  $($result.InstallAction)" }
        Write-Host "Files:   $($result.FileCount)"
        Write-Host "SHA-256: $($result.Sha256)"
    }
    if ($PassThru) { $result }
}
finally {
    $archive.Dispose()
}
