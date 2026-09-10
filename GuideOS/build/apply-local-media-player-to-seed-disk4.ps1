$ErrorActionPreference = 'Stop'

$diskNumber = 4
$expectedName = 'TS-RDF5 SD  Transcend'
$expectedSerial = '00000000TS38'
$expectedSize = 62239277056L
$rootOffset = 163577856L
$rootLength = 2147483648L
$expectedPartitionSize = 5368709120L
$physicalPath = '\\.\PhysicalDrive4'
$capturePath = 'G:\GuideOS-private\muos-reference\seed-before-local-media-player-rootfs.ext4'
$imagePath = 'G:\GuideOS-private\muos-reference\seed-local-media-player-live-rootfs.ext4'
$prepareScript = '/mnt/e/DGttG/HGttG_vol1/GuideOS/build/prepare-local-media-player-rootfs.sh'
$resultPath = Join-Path $PSScriptRoot 'apply-local-media-player-result.txt'
$prepareOutput = Join-Path $PSScriptRoot 'prepare-local-media-player-stdout.txt'
$prepareError = Join-Path $PSScriptRoot 'prepare-local-media-player-stderr.txt'
$source = $null
$target = $null

function Confirm-GuideSeed {
    $disk = Get-Disk -Number $diskNumber
    $root = Get-Partition -DiskNumber $diskNumber -PartitionNumber 5
    if ($disk.FriendlyName -ne $expectedName -or
        $disk.SerialNumber.Trim() -ne $expectedSerial -or
        $disk.Size -ne $expectedSize -or
        $disk.BusType -ne 'USB' -or
        $disk.PartitionStyle -ne 'GPT' -or
        $disk.IsBoot -or $disk.IsSystem -or $disk.IsOffline -or
        $root.Offset -ne $rootOffset -or
        $root.Size -ne $expectedPartitionSize) {
        throw 'Disk 4 does not exactly match the confirmed GuideOS seed. Nothing was written.'
    }
    if ($disk.IsReadOnly) {
        throw 'The confirmed seed is write-protected. Nothing was written.'
    }
}

function Copy-ExactRegion {
    param(
        [System.IO.Stream]$InputStream,
        [System.IO.Stream]$OutputStream,
        [long]$ByteCount,
        [byte[]]$Buffer
    )
    $remaining = $ByteCount
    while ($remaining -gt 0) {
        $wanted = if ($remaining -gt $Buffer.Length) { $Buffer.Length } else { [int]$remaining }
        $read = $InputStream.Read($Buffer, 0, $wanted)
        if ($read -ne $wanted) { throw 'Unexpected end of data during an exact root-region copy.' }
        $OutputStream.Write($Buffer, 0, $read)
        $remaining -= $read
    }
}

function Get-RegionHash {
    param([string]$DevicePath, [long]$Offset, [long]$ByteCount, [byte[]]$Buffer)
    $stream = [IO.FileStream]::new(
        $DevicePath, [IO.FileMode]::Open, [IO.FileAccess]::Read,
        [IO.FileShare]::ReadWrite, $Buffer.Length, [IO.FileOptions]::SequentialScan)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $stream.Position = $Offset
        $remaining = $ByteCount
        while ($remaining -gt 0) {
            $wanted = if ($remaining -gt $Buffer.Length) { $Buffer.Length } else { [int]$remaining }
            $read = $stream.Read($Buffer, 0, $wanted)
            if ($read -ne $wanted) { throw 'Unexpected end of seed during readback verification.' }
            [void]$sha.TransformBlock($Buffer, 0, $read, $Buffer, 0)
            $remaining -= $read
        }
        [void]$sha.TransformFinalBlock((New-Object byte[] 0), 0, 0)
        return ([BitConverter]::ToString($sha.Hash)).Replace('-', '')
    }
    finally {
        $sha.Dispose()
        $stream.Dispose()
    }
}

Remove-Item -LiteralPath $resultPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $prepareOutput -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $prepareError -Force -ErrorAction SilentlyContinue

try {
    Confirm-GuideSeed
    $chunkSize = 4MB
    $buffer = New-Object byte[] $chunkSize

    # Capture the live filesystem before changing anything. The update is
    # assembled from this copy so local settings and trusted relationships stay.
    $source = [IO.FileStream]::new(
        $physicalPath, [IO.FileMode]::Open, [IO.FileAccess]::Read,
        [IO.FileShare]::ReadWrite, $chunkSize, [IO.FileOptions]::SequentialScan)
    $target = [IO.FileStream]::new(
        $capturePath, [IO.FileMode]::Create, [IO.FileAccess]::Write,
        [IO.FileShare]::None, $chunkSize, [IO.FileOptions]::WriteThrough)
    $source.Position = $rootOffset
    Copy-ExactRegion $source $target $rootLength $buffer
    $target.Flush($true)
    $target.Dispose(); $target = $null
    $source.Dispose(); $source = $null
    $captureHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $capturePath).Hash
    "CAPTURED $captureHash" | Add-Content -LiteralPath $resultPath

    $assembly = Start-Process -FilePath 'wsl.exe' -ArgumentList @(
        '-d', 'Ubuntu', '--', 'env',
        'GUIDE_SOURCE_IMAGE=/mnt/g/GuideOS-private/muos-reference/seed-before-local-media-player-rootfs.ext4',
        'GUIDE_OUTPUT_IMAGE=/mnt/g/GuideOS-private/muos-reference/seed-local-media-player-live-rootfs.ext4',
        'sh', $prepareScript
    ) -Wait -PassThru -NoNewWindow -RedirectStandardOutput $prepareOutput `
      -RedirectStandardError $prepareError
    if (Test-Path -LiteralPath $prepareOutput) {
        Get-Content -LiteralPath $prepareOutput | Add-Content -LiteralPath $resultPath
    }
    if ($assembly.ExitCode -ne 0) {
        if (Test-Path -LiteralPath $prepareError) {
            Get-Content -LiteralPath $prepareError | Add-Content -LiteralPath $resultPath
        }
        throw 'The verified update image could not be assembled. Nothing was written.'
    }
    if ((Get-Item -LiteralPath $imagePath).Length -ne $rootLength) {
        throw 'The prepared root image has the wrong size. Nothing was written.'
    }
    $imageHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $imagePath).Hash
    "PREPARED $imageHash" | Add-Content -LiteralPath $resultPath

    Confirm-GuideSeed
    $mountedLetters = @(Get-Partition -DiskNumber $diskNumber |
        Where-Object { $_.DriveLetter } | ForEach-Object { [string]$_.DriveLetter })
    foreach ($letter in $mountedLetters) {
        & mountvol.exe ($letter + ':') /P
        if ($LASTEXITCODE -ne 0) {
            throw "Could not safely dismount seed volume $letter`: before writing."
        }
    }

    Confirm-GuideSeed
    $source = [IO.FileStream]::new(
        $imagePath, [IO.FileMode]::Open, [IO.FileAccess]::Read,
        [IO.FileShare]::Read, $chunkSize, [IO.FileOptions]::SequentialScan)
    $target = [IO.FileStream]::new(
        $physicalPath, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite,
        [IO.FileShare]::ReadWrite, $chunkSize, [IO.FileOptions]::WriteThrough)
    $target.Position = $rootOffset
    Copy-ExactRegion $source $target $rootLength $buffer
    $target.Flush($true)
    $target.Dispose(); $target = $null
    $source.Dispose(); $source = $null
    'WRITE 100%' | Add-Content -LiteralPath $resultPath

    $readbackHash = Get-RegionHash $physicalPath $rootOffset $rootLength $buffer
    if ($readbackHash -ne $imageHash) {
        throw "Root verification failed: $readbackHash"
    }
    "VERIFIED $readbackHash" | Add-Content -LiteralPath $resultPath
}
catch {
    "FAILED $($_.Exception.Message)" | Add-Content -LiteralPath $resultPath
    throw
}
finally {
    if ($source) { $source.Dispose() }
    if ($target) { $target.Dispose() }
}
