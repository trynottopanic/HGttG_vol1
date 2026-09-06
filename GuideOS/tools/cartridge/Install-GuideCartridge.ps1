[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $Cartridge,
    [Parameter(Mandatory = $true)] [string] $CardRoot,
    [switch] $Force
)

$ErrorActionPreference = 'Stop'

function ConvertTo-GuideCardText {
    param([string] $Text)
    $characters = foreach ($character in $Text.ToCharArray()) {
        $number = [int]$character
        if ($number -ge 32 -and $number -le 126) { $character } else { ' ' }
    }
    return (-join $characters).Trim()
}

$testTool = Join-Path $PSScriptRoot 'Test-GuideCartridge.ps1'
$checked = & $testTool -Path $Cartridge -Quiet -PassThru
$root = (Resolve-Path -LiteralPath $CardRoot).Path
if (-not (Test-Path -LiteralPath $root -PathType Container)) { throw 'CardRoot must be a mounted folder or drive.' }

$destinationFolder = Join-Path $root 'GUIDE\CARTRIDGES'
[System.IO.Directory]::CreateDirectory($destinationFolder) | Out-Null
$baseName = $checked.Id + '-' + $checked.Version
$destination = Join-Path $destinationFolder ($baseName + '.guide')
$partial = $destination + '.partial'
$indexDestination = Join-Path $destinationFolder ($baseName + '.gde')
$indexPartial = $indexDestination + '.partial'
if ((Test-Path -LiteralPath $destination) -and -not $Force) {
    throw "That cartridge version is already on the card. Use -Force to replace it."
}
try {
    Copy-Item -LiteralPath $checked.Path -Destination $partial -Force
    $copied = & $testTool -Path $partial -Quiet -PassThru
    if ($copied.Sha256 -ne $checked.Sha256) { throw 'The card copy does not match the source cartridge.' }
    if (Test-Path -LiteralPath $destination) { Remove-Item -LiteralPath $destination -Force }
    Move-Item -LiteralPath $partial -Destination $destination

    $cardName = ConvertTo-GuideCardText $checked.Name
    if (-not $cardName) { $cardName = $checked.Id }
    $cardSummary = ConvertTo-GuideCardText $checked.Summary
    $indexLines = @(
        'GUIDE-CARTRIDGE-INDEX-1',
        "ID=$($checked.Id)",
        "NAME=$cardName",
        "VERSION=$($checked.Version)",
        "KIND=$($checked.Kind)",
        "SUMMARY=$cardSummary",
        "FILE=$([System.IO.Path]::GetFileName($destination))",
        "BYTES=$((Get-Item -LiteralPath $destination).Length)",
        "SHA256=$($checked.Sha256)"
    )
    foreach ($capability in @($checked.Capabilities)) { $indexLines += "CAPABILITY=$capability" }
    if ($checked.InstallAction) { $indexLines += "ACTION=$($checked.InstallAction)" }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($indexPartial, (($indexLines -join "`n") + "`n"), $utf8)
    if (Test-Path -LiteralPath $indexDestination) { Remove-Item -LiteralPath $indexDestination -Force }
    Move-Item -LiteralPath $indexPartial -Destination $indexDestination
}
finally {
    if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Force }
    if (Test-Path -LiteralPath $indexPartial) { Remove-Item -LiteralPath $indexPartial -Force }
}

Write-Host ''
Write-Host 'CARTRIDGE COPIED SAFELY' -ForegroundColor Green
Write-Host "Card file: $destination"
Write-Host "Card index: $indexDestination"
Write-Host "SHA-256:  $($checked.Sha256)"
