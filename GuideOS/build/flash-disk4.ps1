$ErrorActionPreference = 'Stop'
$transcriptPath = "$PSScriptRoot\flash-transcript.txt"
Start-Transcript -LiteralPath $transcriptPath -Force

Add-Type @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

public static class GuideVolumeControl {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool DeviceIoControl(
        SafeFileHandle device, uint controlCode,
        IntPtr input, uint inputSize,
        IntPtr output, uint outputSize,
        out uint bytesReturned, IntPtr overlapped);
}
'@

function Invoke-VolumeControl($stream, [uint32]$controlCode, [string]$operation) {
    [uint32]$returned = 0
    $ok = [GuideVolumeControl]::DeviceIoControl(
        $stream.SafeFileHandle, $controlCode,
        [IntPtr]::Zero, 0, [IntPtr]::Zero, 0,
        [ref]$returned, [IntPtr]::Zero)
    if (-not $ok) {
        $code = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
        throw "$operation failed with Windows error $code. Nothing was written."
    }
}

$diskNumber = 4
$expectedSerial = '00000000TS38'
$expectedSize = 62239277056
$expectedHash = '1F4166A488C96494075D412805F8FB6A47078F96CE80D144CD3D7DBD1FC56256'
$imagePath = (Resolve-Path -LiteralPath "$PSScriptRoot\GuideOS-RG35XXH-ddr4.img").Path
$physicalPath = "\\.\PhysicalDrive$diskNumber"

function Read-Exactly($stream, [byte[]]$destination, [int]$count) {
    $offset = 0
    while ($offset -lt $count) {
        $readNow = $stream.Read($destination, $offset, $count - $offset)
        if ($readNow -le 0) { throw 'Unexpected end of input.' }
        $offset += $readNow
    }
}

$disk = Get-Disk -Number $diskNumber
if ($disk.SerialNumber.Trim() -ne $expectedSerial -or
    $disk.Size -ne $expectedSize -or
    $disk.BusType -ne 'USB' -or
    $disk.IsBoot -or $disk.IsSystem) {
    throw 'Disk 4 no longer matches the confirmed Transcend microSD adapter. Nothing was written.'
}
if ($disk.IsReadOnly) {
    throw 'Disk 4 is write-protected. Nothing was written.'
}

$actualImageHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $imagePath).Hash
if ($actualImageHash -ne $expectedHash) {
    throw 'The image checksum changed. Nothing was written.'
}

$bufferSize = 4MB
$buffer = New-Object byte[] $bufferSize
$zeros = New-Object byte[] 1MB
$source = $null
$target = $null
$volumeLocks = @()

try {
    $volumePaths = @(
        Get-Partition -DiskNumber $diskNumber |
            ForEach-Object { $_.AccessPaths } |
            Where-Object { $_ -like '\\?\Volume{*}\' }
    )
    $mountedVolumes = @(Get-Volume | Where-Object { $_.Path -in $volumePaths })
    foreach ($volume in $mountedVolumes) {
        & fsutil.exe volume dismount $volume.Path
        if ($LASTEXITCODE -ne 0) {
            throw "Could not dismount $($volume.Path). Nothing was written."
        }
    }

    foreach ($volumePath in $volumePaths) {
        $lockPath = $volumePath.TrimEnd('\')
        $lock = [System.IO.FileStream]::new(
            $lockPath,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::ReadWrite)
        Invoke-VolumeControl $lock 0x00090018 "Locking $lockPath"
        Invoke-VolumeControl $lock 0x00090020 "Dismounting $lockPath"
        $volumeLocks += $lock
    }

    $source = [System.IO.FileStream]::new(
        $imagePath,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::Read,
        $bufferSize,
        [System.IO.FileOptions]::RandomAccess)
    $target = [System.IO.FileStream]::new(
        $physicalPath,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::ReadWrite,
        $bufferSize,
        [System.IO.FileOptions]::WriteThrough)

    # Write from the end toward the beginning, leaving the MBR and primary GPT
    # header until last. This prevents Windows from rescanning removable media
    # and invalidating the raw-device handle halfway through the copy.
    $imageLength = $source.Length
    $bootRecordLength = 1024
    $position = $imageLength
    while ($position -gt $bootRecordLength) {
        $remainingToWrite = $position - $bootRecordLength
        if ($remainingToWrite -gt $buffer.Length) {
            $writeSize = $buffer.Length
        }
        else {
            $writeSize = [int]$remainingToWrite
        }
        $position -= $writeSize
        $source.Position = $position
        Read-Exactly $source $buffer $writeSize
        $target.Position = $position
        $target.Write($buffer, 0, $writeSize)
        $written = $imageLength - $position
        if (($written % 256MB) -lt $bufferSize) {
            $percent = [math]::Floor(100 * $written / $imageLength)
            Write-Output "WRITE $percent% ($written of $imageLength bytes)"
        }
    }

    # Clear stale partition metadata immediately after the image and at the
    # physical end of a previously used card.
    $target.Position = $imageLength
    $target.Write($zeros, 0, $zeros.Length)
    $target.Position = $disk.Size - $zeros.Length
    $target.Write($zeros, 0, $zeros.Length)

    $source.Position = 0
    Read-Exactly $source $buffer $bootRecordLength
    $target.Position = 0
    $target.Write($buffer, 0, $bootRecordLength)
    $target.Flush($true)
    Write-Output "WRITE 100% ($imageLength of $imageLength bytes)"

    $target.Dispose()
    $target = $null
    Start-Sleep -Seconds 3
    $target = [System.IO.FileStream]::new(
        $physicalPath,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::ReadWrite,
        $bufferSize,
        [System.IO.FileOptions]::SequentialScan)

    $target.Position = 0
    $remaining = $imageLength
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        while ($remaining -gt 0) {
            if ($remaining -gt $buffer.Length) {
                $wanted = $buffer.Length
            }
            else {
                $wanted = [int]$remaining
            }
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

    if ($cardHash -ne $expectedHash) {
        throw "Verification failed. Card hash: $cardHash"
    }
    Write-Output "VERIFIED $cardHash"
}
finally {
    if ($source) { $source.Dispose() }
    if ($target) { $target.Dispose() }
    foreach ($lock in $volumeLocks) {
        try {
            [uint32]$returned = 0
            [void][GuideVolumeControl]::DeviceIoControl(
                $lock.SafeFileHandle, 0x0009001C,
                [IntPtr]::Zero, 0, [IntPtr]::Zero, 0,
                [ref]$returned, [IntPtr]::Zero)
        }
        finally {
            $lock.Dispose()
        }
    }
}

Stop-Transcript
