# SPDX-License-Identifier: AGPL-3.0-or-later
param(
    [string]$OutputDirectory = "$PSScriptRoot\dist"
)

$ErrorActionPreference = "Stop"

python -m unittest discover -s "$PSScriptRoot\tests" -v
python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --name ThirdWayNode `
    --distpath $OutputDirectory `
    --workpath "$env:TEMP\thirdway-host-build" `
    --specpath "$env:TEMP\thirdway-host-spec" `
    "$PSScriptRoot\thirdway_host.py"

python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --name ThirdWayDeck `
    --distpath $OutputDirectory `
    --workpath "$env:TEMP\thirdway-deck-build" `
    --specpath "$env:TEMP\thirdway-deck-spec" `
    "$PSScriptRoot\thirdway_deck.py"

Write-Host "Built $OutputDirectory\ThirdWayNode.exe"
Write-Host "Built $OutputDirectory\ThirdWayDeck.exe"
