$ErrorActionPreference = 'Stop'

$diskNumber = 4
$expectedSerial = '00000000TS38'
$expectedSize = 62239277056
$expectedHash = '1F4166A488C96494075D412805F8FB6A47078F96CE80D144CD3D7DBD1FC56256'
$imagePath = (Resolve-Path -LiteralPath "$PSScriptRoot\GuideOS-RG35XXH-ddr4.img").Path
$imagerPath = 'C:\Program Files\Raspberry Pi Ltd\Imager\rpi-imager.exe'
$imagerCliPath = 'C:\Program Files\Raspberry Pi Ltd\Imager\rpi-imager-cli.cmd'
$destination = "\\.\PhysicalDrive$diskNumber"
$logPath = "$PSScriptRoot\imager-flash-output.txt"

$disk = Get-Disk -Number $diskNumber
if ($disk.SerialNumber.Trim() -ne $expectedSerial -or
    $disk.Size -ne $expectedSize -or
    $disk.BusType -ne 'USB' -or
    $disk.IsBoot -or $disk.IsSystem -or $disk.IsReadOnly) {
    throw 'Disk 4 no longer matches the confirmed writable Transcend microSD adapter.'
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $imagePath).Hash -ne $expectedHash) {
    throw 'The GuideOS image checksum changed. Nothing was written.'
}
if (-not (Test-Path -LiteralPath $imagerPath)) {
    throw 'Raspberry Pi Imager is not installed at the expected path.'
}
if (-not (Test-Path -LiteralPath $imagerCliPath)) {
    throw 'Raspberry Pi Imager CLI wrapper is missing.'
}

$imagerDirectory = Split-Path -Parent $imagerPath
Push-Location $imagerDirectory
try {
    & $imagerCliPath --debug --disable-telemetry --sha256 $expectedHash $imagePath $destination
    $imagerExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}
@(
    "IMAGER_EXIT_CODE=$imagerExitCode"
    "IMAGE=$imagePath"
    "DESTINATION=$destination"
) | Set-Content -LiteralPath $logPath -Encoding ASCII
exit $imagerExitCode
