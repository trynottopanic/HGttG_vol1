$ErrorActionPreference = 'Stop'

$diskNumber = 4
$expectedModel = 'TS-RDF5 SD  Transcend'
$expectedSerial = '00000000TS38'
$expectedSize = 250399948800
$captureLength = 163577856L
$physicalPath = '\\.\PhysicalDrive4'
$privateRoot = 'G:\GuideOS-private\muos-reference'
$capturePath = Join-Path $privateRoot 'muos-boot-prefix-163577856.img'
$resultPath = Join-Path $PSScriptRoot 'capture-muos-reference-result.txt'

$disk = Get-Disk -Number $diskNumber
if ($disk.FriendlyName -ne $expectedModel -or
    $disk.SerialNumber.Trim() -ne $expectedSerial -or
    $disk.Size -ne $expectedSize -or
    $disk.NumberOfPartitions -ne 6 -or
    $disk.IsBoot -or $disk.IsSystem) {
    throw 'Disk 4 does not match the confirmed 250 GB muOS reference card.'
}

New-Item -ItemType Directory -Path $privateRoot -Force | Out-Null
$buffer = New-Object byte[] 4MB
$source = $null
$target = $null
try {
    $source = [IO.FileStream]::new(
        $physicalPath, [IO.FileMode]::Open, [IO.FileAccess]::Read,
        [IO.FileShare]::ReadWrite, 4MB, [IO.FileOptions]::SequentialScan)
    $target = [IO.FileStream]::new(
        $capturePath, [IO.FileMode]::Create, [IO.FileAccess]::Write,
        [IO.FileShare]::None, 4MB, [IO.FileOptions]::SequentialScan)
    $remaining = $captureLength
    while ($remaining -gt 0) {
        $wanted = [int][Math]::Min($buffer.Length, $remaining)
        $read = $source.Read($buffer, 0, $wanted)
        if ($read -ne $wanted) { throw 'Unexpected short read from the muOS card.' }
        $target.Write($buffer, 0, $read)
        $remaining -= $read
    }
    $target.Flush($true)
}
finally {
    if ($source) { $source.Dispose() }
    if ($target) { $target.Dispose() }
}

$latestDmesg = Get-ChildItem -LiteralPath 'I:\MUOS\log\dmesg' -File |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($latestDmesg) {
    Copy-Item -LiteralPath $latestDmesg.FullName -Destination (Join-Path $privateRoot 'known-good-dmesg.log') -Force
}

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $capturePath).Hash
@(
    'CAPTURE_OK'
    "PATH=$capturePath"
    "BYTES=$captureLength"
    "SHA256=$hash"
    'USER_DATA_PARTITION_INCLUDED=False'
) | Set-Content -LiteralPath $resultPath -Encoding ascii

