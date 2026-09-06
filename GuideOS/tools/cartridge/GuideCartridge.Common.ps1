Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Get-GuideSha256FromStream {
    param([Parameter(Mandatory = $true)] [System.IO.Stream] $Stream)

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hash = $sha.ComputeHash($Stream)
        return ([System.BitConverter]::ToString($hash)).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Get-GuideSha256FromFile {
    param([Parameter(Mandatory = $true)] [string] $Path)

    $stream = [System.IO.File]::OpenRead($Path)
    try {
        return Get-GuideSha256FromStream -Stream $stream
    }
    finally {
        $stream.Dispose()
    }
}

function Assert-GuideEntryPath {
    param([Parameter(Mandatory = $true)] [string] $Path)

    if ([string]::IsNullOrWhiteSpace($Path) -or
        $Path.StartsWith('/') -or
        $Path.StartsWith('\') -or
        $Path.Contains('\') -or
        $Path.Contains(':') -or
        $Path.Contains("`0") -or
        $Path -match '(^|/)\.\.(/|$)' -or
        $Path -match '(^|/)\.(/|$)') {
        throw "Unsafe cartridge path: $Path"
    }
}

function Assert-GuideIdentifier {
    param([Parameter(Mandatory = $true)] [string] $Id)

    if ($Id.Length -gt 64 -or $Id -notmatch '^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$') {
        throw "Package id must be 1-64 lowercase letters, numbers, dots, or hyphens."
    }
}

function Assert-GuideVersion {
    param([Parameter(Mandatory = $true)] [string] $Version)

    if ($Version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$') {
        throw "Version must look like 1.0.0 or 1.0.0-preview.1."
    }
}

function Import-GuideCompressionAssemblies {
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
}

function Get-GuideCompressionLevel {
    param([Parameter(Mandatory = $true)] [string] $Path)

    $alreadyCompressed = @(
        '.7z', '.aac', '.avi', '.flac', '.gif', '.gz', '.jpeg', '.jpg', '.m4a',
        '.mkv', '.mov', '.mp3', '.mp4', '.ogg', '.png', '.webm', '.webp', '.zip'
    )
    if ($alreadyCompressed -contains [System.IO.Path]::GetExtension($Path).ToLowerInvariant()) {
        return [System.IO.Compression.CompressionLevel]::NoCompression
    }
    return [System.IO.Compression.CompressionLevel]::Optimal
}
