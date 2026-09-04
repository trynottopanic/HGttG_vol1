# SPDX-License-Identifier: AGPL-3.0-or-later
$ErrorActionPreference = "Stop"

$compilerCandidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 7\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe"
)
$compiler = $compilerCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $compiler) {
    throw "Inno Setup 7 was not found. Install JRSoftware.InnoSetup.7 with winget."
}

& "$PSScriptRoot\build_windows.ps1" -OutputDirectory "$PSScriptRoot\dist"
if ($LASTEXITCODE -ne 0) {
    throw "The Windows program build failed with exit code $LASTEXITCODE."
}
& $compiler "$PSScriptRoot\installer\ThirdWayNode.iss"
if ($LASTEXITCODE -ne 0) {
    throw "The installer build failed with exit code $LASTEXITCODE."
}

Write-Host "Built $PSScriptRoot\installer-dist\ThirdWayNode-Setup-0.1.0.exe"
