$ErrorActionPreference = 'Stop'

$diskNumber = 4
$expectedName = 'TS-RDF5 SD  Transcend'
$expectedSerial = '00000000TS38'
$expectedSize = 62239277056L
$rootOffset = 163577856L
$rootLength = 2147483648L
$expectedPartitionSize = 5368709120L
$physicalPath = '\\.\PhysicalDrive4'
$outputPath = 'G:\GuideOS-private\muos-reference\seed-bluetooth-live-base-rootfs.ext4'
$resultPath = Join-Path $PSScriptRoot 'capture-bluetooth-base-result.txt'

$source = $null
$target = $null
$sha = $null

try {
    $disk = Get-Disk -Number $diskNumber
    $root = Get-Partition -DiskNumber $diskNumber -PartitionNumber 5
    if ($disk.FriendlyName -ne $expectedName -or
        $disk.SerialNumber.Trim() -ne $expectedSerial -or
        $disk.Size -ne $expectedSize -or
        $disk.BusType -ne 'USB' -or $disk.IsBoot -or $disk.IsSystem -or
        $root.Offset -ne $rootOffset -or $root.Size -ne $expectedPartitionSize) {
        throw 'Disk 4 does not exactly match the confirmed GuideOS seed. Nothing was read.'
    }

    $chunkSize = 4MB
    $buffer = New-Object byte[] $chunkSize
    $source = [IO.FileStream]::new(
        $physicalPath, [IO.FileMode]::Open, [IO.FileAccess]::Read,
        [IO.FileShare]::ReadWrite, $chunkSize, [IO.FileOptions]::SequentialScan)
    $target = [IO.FileStream]::new(
        $outputPath, [IO.FileMode]::Create, [IO.FileAccess]::Write,
        [IO.FileShare]::None, $chunkSize, [IO.FileOptions]::WriteThrough)
    $source.Position = $rootOffset
    $remaining = $rootLength
    $sha = [Security.Cryptography.SHA256]::Create()
    while ($remaining -gt 0) {
        $wanted = if ($remaining -gt $chunkSize) { $chunkSize } else { [int]$remaining }
        $read = $source.Read($buffer, 0, $wanted)
        if ($read -ne $wanted) { throw 'Unexpected end of seed while preserving its root filesystem.' }
        $target.Write($buffer, 0, $read)
        [void]$sha.TransformBlock($buffer, 0, $read, $buffer, 0)
        $remaining -= $read
    }
    [void]$sha.TransformFinalBlock((New-Object byte[] 0), 0, 0)
    $target.Flush($true)
    $hash = ([BitConverter]::ToString($sha.Hash)).Replace('-', '')
    @(
        "CAPTURED=$outputPath"
        "BYTES=$rootLength"
        "SHA256=$hash"
    ) | Set-Content -LiteralPath $resultPath -Encoding ascii
}
catch {
    "FAILED $($_.Exception.Message)" | Set-Content -LiteralPath $resultPath -Encoding ascii
    throw
}
finally {
    if ($source) { $source.Dispose() }
    if ($target) { $target.Dispose() }
    if ($sha) { $sha.Dispose() }
}
