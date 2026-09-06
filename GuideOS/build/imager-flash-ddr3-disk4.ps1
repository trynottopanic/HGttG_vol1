$ErrorActionPreference = 'Stop'

$diskNumber = 4
$expectedModel = 'TS-RDF5 SD  Transcend'
$expectedSerial = '00000000TS38'
$expectedSize = 62239277056
$expectedHash = 'E397679AD14CA7DFE454F5F2E3ADF2B78ECC81B7B576CCFA263F0C3FB60C61E4'
$imagePath = 'E:\DGttG\HGttG_vol1\GuideOS\build\GuideOS-RG35XXH-ddr3.img'
$imagerDirectory = 'C:\Program Files\Raspberry Pi Ltd\Imager'
$imagerPath = Join-Path $imagerDirectory 'rpi-imager.exe'
$destination = "\\.\PhysicalDrive$diskNumber"
$logPath = 'E:\DGttG\HGttG_vol1\GuideOS\build\imager-flash-ddr3-output.txt'
$stdoutPath = 'E:\DGttG\HGttG_vol1\GuideOS\build\imager-flash-ddr3-stdout.txt'
$stderrPath = 'E:\DGttG\HGttG_vol1\GuideOS\build\imager-flash-ddr3-stderr.txt'

$disk = Get-Disk -Number $diskNumber
if ($disk.FriendlyName -ne $expectedModel -or
    $disk.SerialNumber.Trim() -ne $expectedSerial -or
    $disk.Size -ne $expectedSize -or
    $disk.BusType -ne 'USB' -or
    $disk.IsBoot -or $disk.IsSystem -or $disk.IsReadOnly) {
    throw 'Disk 4 no longer matches the confirmed writable Anbernic microSD adapter.'
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $imagePath).Hash -ne $expectedHash) {
    throw 'The DDR3 GuideOS image checksum changed. Nothing was written.'
}
if (-not (Test-Path -LiteralPath $imagerPath)) {
    throw 'Raspberry Pi Imager is missing.'
}

Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
$arguments = "--cli --debug --disable-telemetry --sha256 $expectedHash `"$imagePath`" `"$destination`""
$imager = Start-Process -FilePath $imagerPath `
    -ArgumentList $arguments `
    -WorkingDirectory $imagerDirectory `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -Wait -PassThru
$imagerExitCode = $imager.ExitCode

@(
    "IMAGER_EXIT_CODE=$imagerExitCode"
    "IMAGE=$imagePath"
    "IMAGE_SHA256=$expectedHash"
    "DESTINATION=$destination"
) | Set-Content -LiteralPath $logPath -Encoding ascii
exit $imagerExitCode
