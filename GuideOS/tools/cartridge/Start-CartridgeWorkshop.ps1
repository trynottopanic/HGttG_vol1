[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

function Read-RequiredAnswer {
    param([string] $Question)
    do { $answer = (Read-Host $Question).Trim() } while (-not $answer)
    return $answer
}

function ConvertTo-GuideSlug {
    param([string] $Text)
    $slug = $Text.ToLowerInvariant() -replace '[^a-z0-9]+', '-'
    $slug = $slug.Trim('-')
    if (-not $slug) { $slug = 'cartridge' }
    if ($slug.Length -gt 58) { $slug = $slug.Substring(0, 58).TrimEnd('-') }
    return $slug
}

Write-Host ''
Write-Host 'GUIDE CARTRIDGE WORKSHOP' -ForegroundColor Cyan
Write-Host 'This workshop turns one folder into a shareable .guide file.'
Write-Host 'It will not change the original folder.'
Write-Host ''

$source = Read-RequiredAnswer 'Folder containing the cartridge files'
if (-not (Test-Path -LiteralPath $source -PathType Container)) {
    throw "That folder was not found: $source"
}
$name = Read-RequiredAnswer 'Name people should see'
$suggestedId = 'local.' + (ConvertTo-GuideSlug -Text $name)
$id = (Read-Host "Permanent package id [$suggestedId]").Trim()
if (-not $id) { $id = $suggestedId }
$version = (Read-Host 'Version [1.0.0]').Trim()
if (-not $version) { $version = '1.0.0' }

Write-Host ''
Write-Host 'What is inside?'
Write-Host '  1  Data or documents'
Write-Host '  2  Music, pictures, or video'
Write-Host '  3  A Guide Recipe'
Write-Host '  4  An application (future runtime)'
Write-Host '  5  A device adapter (future runtime)'
$kindAnswer = (Read-Host 'Choose 1-5 [1]').Trim()
if (-not $kindAnswer) { $kindAnswer = '1' }
$kinds = @('data', 'media', 'recipe', 'application', 'adapter')
if ($kindAnswer -notmatch '^[1-5]$') { throw 'Please choose a number from 1 through 5.' }
$kind = $kinds[[int]$kindAnswer - 1]
$summary = (Read-Host 'One-sentence description (optional)').Trim()

$sourceInfo = Get-Item -LiteralPath $source
$suggestedOutput = Join-Path $sourceInfo.Parent.FullName ($id + '-' + $version + '.guide')
$output = (Read-Host "Save the cartridge here [$suggestedOutput]").Trim()
if (-not $output) { $output = $suggestedOutput }

Write-Host ''
Write-Host 'Checking the files and building the cartridge...'
& (Join-Path $PSScriptRoot 'New-GuideCartridge.ps1') `
    -Source $sourceInfo.FullName `
    -Id $id `
    -Name $name `
    -Version $version `
    -Kind $kind `
    -Summary $summary `
    -Output $output

Write-Host ''
Write-Host 'The .guide file is ready to share. Its .sha256 companion is a change detector.'

