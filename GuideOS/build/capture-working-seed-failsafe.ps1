$ErrorActionPreference = 'Stop'

$diskNumber = 4
$expectedModel = 'TS-RDF5 SD  Transcend'
$expectedSerial = '00000000TS38'
$expectedSize = 62239277056L
$expectedPartitionCount = 6
$captureLength = 6442450944L
$physicalPath = '\\.\PhysicalDrive4'
$privateRoot = 'E:\DGttG\private-recovery'
$capturePath = Join-Path $privateRoot 'guideos-seed-failsafe-2026-09-06.img'
$manifestPath = Join-Path $privateRoot 'guideos-seed-failsafe-2026-09-06.txt'

function Get-RangeHash([string]$Path, [long]$Length) {
    $buffer = New-Object byte[] 8MB
    $stream = $null
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $stream = [IO.FileStream]::new(
            $Path, [IO.FileMode]::Open, [IO.FileAccess]::Read,
            [IO.FileShare]::ReadWrite, 8MB, [IO.FileOptions]::SequentialScan)
        $remaining = $Length
        while ($remaining -gt 0) {
            $wanted = [int][Math]::Min([long]$buffer.Length, [long]$remaining)
            $read = $stream.Read($buffer, 0, $wanted)
            if ($read -ne $wanted) { throw "Unexpected short read from $Path" }
            [void]$sha.TransformBlock($buffer, 0, $read, $null, 0)
            $remaining -= $read
        }
        [void]$sha.TransformFinalBlock([byte[]]::new(0), 0, 0)
        return ([BitConverter]::ToString($sha.Hash)).Replace('-', '')
    }
    finally {
        if ($stream) { $stream.Dispose() }
        $sha.Dispose()
    }
}

$disk = Get-Disk -Number $diskNumber
$partitions = @(Get-Partition -DiskNumber $diskNumber | Sort-Object Offset)
if ($disk.FriendlyName -ne $expectedModel -or
    $disk.SerialNumber.Trim() -ne $expectedSerial -or
    $disk.Size -ne $expectedSize -or
    $disk.PartitionStyle -ne 'GPT' -or
    $partitions.Count -ne $expectedPartitionCount -or
    $disk.IsBoot -or $disk.IsSystem) {
    throw 'Disk 4 does not match the confirmed working GuideOS seed boundary.'
}
$lastPartitionEnd = ($partitions | ForEach-Object { $_.Offset + $_.Size } |
    Measure-Object -Maximum).Maximum
if ($lastPartitionEnd -gt $captureLength) {
    throw 'A seed partition extends beyond the guarded 6 GiB capture boundary.'
}
$destination = Get-Volume -DriveLetter E
if ($destination.SizeRemaining -lt ($captureLength + 1GB)) {
    throw 'The destination SSD does not have enough free space for the failsafe image.'
}

New-Item -ItemType Directory -Path $privateRoot -Force | Out-Null
if (Test-Path -LiteralPath $capturePath) {
    throw "Failsafe already exists; refusing to overwrite: $capturePath"
}

$buffer = New-Object byte[] 8MB
$source = $null
$target = $null
try {
    $source = [IO.FileStream]::new(
        $physicalPath, [IO.FileMode]::Open, [IO.FileAccess]::Read,
        [IO.FileShare]::ReadWrite, 8MB, [IO.FileOptions]::SequentialScan)
    $target = [IO.FileStream]::new(
        $capturePath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write,
        [IO.FileShare]::None, 8MB, [IO.FileOptions]::SequentialScan)
    $remaining = $captureLength
    $copied = 0L
    $nextProgress = 10
    while ($remaining -gt 0) {
        $wanted = [int][Math]::Min([long]$buffer.Length, [long]$remaining)
        $read = $source.Read($buffer, 0, $wanted)
        if ($read -ne $wanted) { throw 'Unexpected short read from the working seed.' }
        $target.Write($buffer, 0, $read)
        $remaining -= $read
        $copied += $read
        $percent = [int](100 * $copied / $captureLength)
        if ($percent -ge $nextProgress) {
            "CAPTURE $nextProgress%"
            $nextProgress += 10
        }
    }
    $target.Flush($true)
}
finally {
    if ($source) { $source.Dispose() }
    if ($target) { $target.Dispose() }
}

"HASHING SAVED IMAGE"
$imageHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $capturePath).Hash
"HASHING SOURCE AGAIN"
$sourceHash = Get-RangeHash -Path $physicalPath -Length $captureLength
if ($sourceHash -ne $imageHash) {
    throw "Failsafe verification failed: image=$imageHash source=$sourceHash"
}

$partitionLines = $partitions | ForEach-Object {
    "PARTITION=$($_.PartitionNumber),OFFSET=$($_.Offset),SIZE=$($_.Size),TYPE=$($_.Type)"
}
@(
    'CAPTURE_OK'
    "SOURCE_DISK=$diskNumber"
    "SOURCE_MODEL=$($disk.FriendlyName)"
    "SOURCE_SERIAL=$($disk.SerialNumber.Trim())"
    "SOURCE_SIZE=$($disk.Size)"
    "CAPTURE_BYTES=$captureLength"
    "LAST_PARTITION_END=$lastPartitionEnd"
    "IMAGE=$capturePath"
    "SHA256=$imageHash"
    $partitionLines
) | Set-Content -LiteralPath $manifestPath -Encoding ascii

"VERIFIED $imageHash"
"IMAGE $capturePath"
"MANIFEST $manifestPath"
