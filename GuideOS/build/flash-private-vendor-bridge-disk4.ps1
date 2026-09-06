$ErrorActionPreference = 'Stop'

$diskNumber = 4
$expectedName = 'TS-RDF5 SD  Transcend'
$expectedSerial = '00000000TS38'
$expectedSize = 62239277056L
$expectedHash = '97467834AFA6522238ABEB6D3747B5B033019C323490CBF78F53EBD5C67BC821'
$imageLength = 6442450944L
$imagePath = 'G:\GuideOS-private\muos-reference\GuideOS-RG35XXH-private-vendor-bridge.img'
$physicalPath = '\\.\PhysicalDrive4'
$resultPath = Join-Path $PSScriptRoot 'flash-private-vendor-bridge-result.txt'

Add-Type @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

public static class GuideBridgeDiskControl {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool DeviceIoControl(
        SafeFileHandle device, uint controlCode,
        IntPtr input, uint inputSize,
        IntPtr output, uint outputSize,
        out uint bytesReturned, IntPtr overlapped);
}
'@

function Enable-FullRawAccess($stream) {
    [uint32]$returned = 0
    $ok = [GuideBridgeDiskControl]::DeviceIoControl(
        $stream.SafeFileHandle, 0x00090083,
        [IntPtr]::Zero, 0, [IntPtr]::Zero, 0,
        [ref]$returned, [IntPtr]::Zero)
    if (-not $ok) {
        $code = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
        throw "Enabling full raw-disk access failed with Windows error $code."
    }
}

function Read-Exactly($stream, [byte[]]$buffer, [int]$count) {
    $offset = 0
    while ($offset -lt $count) {
        $read = $stream.Read($buffer, $offset, $count - $offset)
        if ($read -le 0) { throw 'Unexpected end of input.' }
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
        throw 'Disk 4 does not match the confirmed expendable 64 GB seed. Nothing was written.'
    }
    if ($disk.IsReadOnly) { throw 'The seed is write-protected. Nothing was written.' }

    $image = Get-Item -LiteralPath $imagePath
    if ($image.Length -ne $imageLength) { throw 'The private image size changed. Nothing was written.' }
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $imagePath).Hash
    if ($actualHash -ne $expectedHash) { throw 'The private image checksum changed. Nothing was written.' }

    # Remove the old test layout only after every identity and image check has
    # passed.  This also prevents Windows from holding its old volumes open.
    Clear-Disk -Number $diskNumber -RemoveData -RemoveOEM -Confirm:$false
    Start-Sleep -Seconds 2

    $chunkSize = 4MB
    $deferredBytes = 1MB
    $buffer = New-Object byte[] $chunkSize
    $source = [IO.FileStream]::new(
        $imagePath, [IO.FileMode]::Open, [IO.FileAccess]::Read,
        [IO.FileShare]::Read, $chunkSize, [IO.FileOptions]::RandomAccess)
    $target = [IO.FileStream]::new(
        $physicalPath, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite,
        [IO.FileShare]::ReadWrite, $chunkSize, [IO.FileOptions]::WriteThrough)
    # Write backward and publish the partition table last, preventing Windows
    # from rescanning the device while its contents are still incomplete.
    $position = $imageLength
    $nextReport = 10
    while ($position -gt $deferredBytes) {
        $remainingToWrite = $position - $deferredBytes
        if ($remainingToWrite -gt $chunkSize) { $writeSize = $chunkSize }
        else { $writeSize = [int]$remainingToWrite }
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

    $source.Position = 0
    Read-Exactly $source $buffer $deferredBytes
    $target.Position = 0
    $target.Write($buffer, 0, $deferredBytes)
    $target.Flush($true)
    $target.Dispose()
    $target = $null
    $source.Dispose()
    $source = $null
    'WRITE 100%' | Add-Content -LiteralPath $resultPath

    Start-Sleep -Seconds 3
    $target = [IO.FileStream]::new(
        $physicalPath, [IO.FileMode]::Open, [IO.FileAccess]::Read,
        [IO.FileShare]::ReadWrite, $chunkSize, [IO.FileOptions]::SequentialScan)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $remaining = $imageLength
        while ($remaining -gt 0) {
            if ($remaining -gt $chunkSize) { $wanted = $chunkSize }
            else { $wanted = [int]$remaining }
            $read = $target.Read($buffer, 0, $wanted)
            if ($read -le 0) { throw 'Unexpected end of card during verification.' }
            [void]$sha.TransformBlock($buffer, 0, $read, $buffer, 0)
            $remaining -= $read
        }
        [void]$sha.TransformFinalBlock((New-Object byte[] 0), 0, 0)
        $cardHash = ([BitConverter]::ToString($sha.Hash)).Replace('-', '')
    }
    finally {
        $sha.Dispose()
    }
    if ($cardHash -ne $expectedHash) { throw "Verification failed: $cardHash" }
    "VERIFIED $cardHash" | Add-Content -LiteralPath $resultPath
}
catch {
    "FAILED $($_.Exception.Message)" | Add-Content -LiteralPath $resultPath
    throw
}
finally {
    if ($source) { $source.Dispose() }
    if ($target) { $target.Dispose() }
}
