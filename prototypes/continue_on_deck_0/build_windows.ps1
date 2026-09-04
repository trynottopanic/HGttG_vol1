# SPDX-License-Identifier: AGPL-3.0-or-later
$ErrorActionPreference = "Stop"
$output = Join-Path $PSScriptRoot "dist"
$build = Join-Path $env:TEMP "thirdway-continue-node-build"
$spec = Join-Path $env:TEMP "thirdway-continue-node-spec"

python -m unittest -v test_deck_receiver.py test_end_to_end.py test_node_player.py test_deck_runtime.py
if ($LASTEXITCODE -ne 0) { throw "Protocol tests failed with exit code $LASTEXITCODE." }

python -m PyInstaller --noconfirm --clean --onefile --name ThirdWayNodePlayer `
    --distpath $output --workpath $build --specpath $spec `
    (Join-Path $PSScriptRoot "node_player.py")
if ($LASTEXITCODE -ne 0) { throw "Windows packaging failed with exit code $LASTEXITCODE." }

Write-Host "Built $output\ThirdWayNodePlayer.exe"
