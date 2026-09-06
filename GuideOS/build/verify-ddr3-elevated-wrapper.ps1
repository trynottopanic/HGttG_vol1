$ErrorActionPreference = 'Continue'
$resultPath = Join-Path $PSScriptRoot 'verify-ddr3-elevated-result.txt'
$verifierPath = Join-Path $PSScriptRoot 'verify-ddr3-disk4.ps1'
Remove-Item -LiteralPath $resultPath -Force -ErrorAction SilentlyContinue
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $verifierPath *>&1 |
    Out-File -LiteralPath $resultPath -Encoding utf8
exit $LASTEXITCODE
