$ErrorActionPreference = 'Stop'

$diskNumber = 4
$expectedName = 'TS-RDF5 SD  Transcend'
$expectedSerial = '00000000TS38'
$expectedSize = 62239277056
$expectedHash = 'E397679AD14CA7DFE454F5F2E3ADF2B78ECC81B7B576CCFA263F0C3FB60C61E4'
$imagePath = (Resolve-Path -LiteralPath "$PSScriptRoot\GuideOS-RG35XXH-ddr3.img").Path
$physicalPath = "\\.\PhysicalDrive$diskNumber"
$resultPath = Join-Path $PSScriptRoot 'flash-ddr3-raw-result.txt'

Add-Type @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

public static class GuideRawDiskControl {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool DeviceIoControl(
        SafeFileHandle device, uint controlCode,
        IntPtr input, uint inputSize,
        IntPtr output, uint outputSize,
        out uint bytesReturned, IntPtr overlapped);
}
'@

function Invoke-DiskControl($stream, [uint32]$controlCode, [string]$operation) {
    [uint32]$returned = 0
    $ok = [GuideRawDiskControl]::DeviceIoControl(
        $stream.SafeFileHandle, $controlCode,
        [IntPtr]::Zero, 0, [IntPtr]::Zero, 0,
        [ref]$returned, [IntPtr]::Zero)
    if (-not $ok) {
        $code = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
        throw "$operation failed with Windows error $code."
    }
}

function Read-Exactly($stream, [byte[]]$buffer, [int]$count) {
    $offset = 0
    while ($offset -lt $count) {
        $read = $stream.Read($buffer, $offset, $count - $offset)
        if ($read -le 0) { throw 'Unexpected end of image.' }
        $offset += $read
    }
}

Remove-Item -LiteralPath $resultPath -Force -ErrorAction SilentlyContinue
$source = $null
$target = $null

try {
    $disk = Get-Disk -Number $diskNumber
    if ($disk.FriendlyName -ne $expectedName -or
        $disk.SerialNumber.Trim() -ne $expectedSerial -or
        $disk.Size -ne $expectedSize -or
        $disk.BusType -ne 'USB' -or
        $disk.IsBoot -or $disk.IsSystem) {
        throw 'Disk 4 no longer matches the confirmed Transcend microSD adapter. Nothing was written.'
    }
    if ($disk.IsReadOnly) { throw 'Disk 4 is write-protected. Nothing was written.' }
    if ($disk.NumberOfPartitions -ne 0) { throw 'Disk 4 is no longer empty. Nothing was written.' }

    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $imagePath).Hash
    if ($actualHash -ne $expectedHash) { throw 'The GuideOS image checksum changed. Nothing was written.' }

    $chunkSize = 4MB
    $deferredBytes = 1MB
    $buffer = New-Object byte[] $chunkSize
    $source = [System.IO.FileStream]::new(
        $imagePath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::Read, $chunkSize, [System.IO.FileOptions]::RandomAccess)
    $target = [System.IO.FileStream]::new(
        $physicalPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::ReadWrite, $chunkSize, [System.IO.FileOptions]::WriteThrough)

    # Permit raw access outside Windows-recognized partition boundaries.
    Invoke-DiskControl $target 0x00090083 'Enabling full raw-disk access'

    # Work backward, keeping the partition table and boot metadata absent until
    # the rest of the image is safely present. This prevents a Windows rescan.
    $imageLength = $source.Length
    $position = $imageLength
    $nextReport = 10
    while ($position -gt $deferredBytes) {
        $writeSize = [int][Math]::Min($chunkSize, $position - $deferredBytes)
        $position -= $writeSize
        $source.Position = $position
        Read-Exactly $source $buffer $writeSize
        $target.Position = $position
        $target.Write($buffer, 0, $writeSize)
        $complete = [int][Math]::Floor(100 * ($imageLength - $position) / $imageLength)
        if ($complete -ge $nextReport) {
            "WRITE $complete%" | Add-Content -LiteralPath $resultPath
            $nextReport += 10
        }
    }

    # Write the first MiB last as one aligned operation.
    $source.Position = 0
    Read-Exactly $source $buffer $deferredBytes
    $target.Position = 0
    $target.Write($buffer, 0, $deferredBytes)
    $target.Flush($true)
    'WRITE 100%' | Add-Content -LiteralPath $resultPath
    'FLASH_WRITE_OK' | Add-Content -LiteralPath $resultPath
}
catch {
    "FLASH_WRITE_FAILED $($_.Exception.Message)" | Add-Content -LiteralPath $resultPath
    exit 1
}
finally {
    if ($source) { $source.Dispose() }
    if ($target) { $target.Dispose() }
}
