$ErrorActionPreference='Stop'
$project=(Get-Item -LiteralPath (Join-Path $PSScriptRoot '../..')).FullName
$output=Join-Path (Get-Item -LiteralPath (Join-Path $project '../..')).FullName 'GuideOS-NDI'
$work=Join-Path (Get-Item -LiteralPath (Join-Path $project '../..')).FullName 'GuideOS-NDI-build'
$source=Join-Path $PSScriptRoot 'guide_ndi.py'
$match=[regex]::Match((Get-Content -LiteralPath $source -Raw),"(?m)^VERSION = '([0-9]+\.[0-9]+\.[0-9]+)'\r?$")
if (-not $match.Success) { throw 'NDI source version is unavailable.' }
$name='GuideOS-NDI-'+$match.Groups[1].Value
$preset=Join-Path $PSScriptRoot 'presets/GuideOS-Deck-480p30.json'
& python -m PyInstaller --noconfirm --onefile --windowed --name $name --distpath $output --workpath $work --specpath $work --add-data ($preset+';presets') $source
if ($LASTEXITCODE -ne 0) { throw 'NDI build failed.' }
$executable=Join-Path $output ($name+'.exe')
$canonical=Join-Path $output 'GuideOS-NDI.exe'
if (Get-Process GuideOS-NDI -ErrorAction SilentlyContinue) {
    Write-Output 'The versioned NDI is ready; the running default executable was left in place.'
} else {
    Copy-Item -LiteralPath $executable -Destination $canonical -Force
}
$receipt=@{version=$match.Groups[1].Value;versionedExecutable=$executable;
    executableSha256=(Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash;
    windowsBuild='successful';completedUtc=[DateTime]::UtcNow.ToString('o')}
$receipt|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $output ('build-receipt-'+$match.Groups[1].Value+'.json')) -Encoding UTF8
if (-not (Get-Process GuideOS-NDI -ErrorAction SilentlyContinue)) {
    $receipt.executable=$canonical
    $receipt|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $output 'build-receipt.json') -Encoding UTF8
}
Get-Item -LiteralPath $executable
