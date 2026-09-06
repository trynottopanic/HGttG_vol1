$ErrorActionPreference = 'Stop'

$diskNumber = 4
$expectedName = 'TS-RDF5 SD  Transcend'
$expectedSerial = '00000000TS38'
$expectedSize = 62239277056L
$rootOffset = 163577856L
$rootLength = 2147483648L
$expectedPartitionSize = 5368709120L
$physicalPath = '\\.\PhysicalDrive4'
$basePath = 'G:\GuideOS-private\muos-reference\seed-media-trust-base-rootfs.ext4'
$imagePath = 'G:\GuideOS-private\muos-reference\seed-media-trust-next-rootfs.ext4'
$resultPath = Join-Path $PSScriptRoot 'apply-media-trust-to-seed-result.txt'
$prepareOutput = Join-Path $PSScriptRoot 'prepare-media-trust-stdout.txt'
$prepareError = Join-Path $PSScriptRoot 'prepare-media-trust-stderr.txt'
$prepareScript = '/mnt/e/DGttG/HGttG_vol1/GuideOS/build/prepare-media-trust-rootfs.sh'

Remove-Item -LiteralPath $resultPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $prepareOutput -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $prepareError -Force -ErrorAction SilentlyContinue
$source = $null
$target = $null

try {
    $disk = Get-Disk -Number $diskNumber
    $root = Get-Partition -DiskNumber $diskNumber -PartitionNumber 5
    if ($disk.FriendlyName -ne $expectedName -or
        $disk.SerialNumber.Trim() -ne $expectedSerial -or
        $disk.Size -ne $expectedSize -or
        $disk.BusType -ne 'USB' -or $disk.IsBoot -or $disk.IsSystem -or
        $root.Offset -ne $rootOffset -or $root.Size -ne $expectedPartitionSize) {
        throw 'Disk 4 does not exactly match the confirmed GuideOS seed. Nothing was written.'
    }
    if ($disk.IsReadOnly) { throw 'The seed is write-protected. Nothing was written.' }

    $chunkSize = 4MB
    $buffer = New-Object byte[] $chunkSize
    $source = [IO.FileStream]::new(
        $physicalPath, [IO.FileMode]::Open, [IO.FileAccess]::Read,
        [IO.FileShare]::ReadWrite, $chunkSize, [IO.FileOptions]::SequentialScan)
    $target = [IO.FileStream]::new(
        $basePath, [IO.FileMode]::Create, [IO.FileAccess]::Write,
        [IO.FileShare]::None, $chunkSize, [IO.FileOptions]::WriteThrough)
    $source.Position = $rootOffset
    $remaining = $rootLength
    while ($remaining -gt 0) {
        $wanted = if ($remaining -gt $chunkSize) { $chunkSize } else { [int]$remaining }
        $read = $source.Read($buffer, 0, $wanted)
        if ($read -ne $wanted) { throw 'Unexpected end of seed while preserving the live root filesystem.' }
        $target.Write($buffer, 0, $read)
        $remaining -= $read
    }
    $target.Flush($true)
    $target.Dispose(); $target = $null
    $source.Dispose(); $source = $null
    $baseHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $basePath).Hash
    "CAPTURED $baseHash" | Add-Content -LiteralPath $resultPath

    $assembly = Start-Process -FilePath 'wsl.exe' -ArgumentList @(
        '-d', 'Ubuntu', '--', 'bash', $prepareScript
    ) -Wait -PassThru -NoNewWindow -RedirectStandardOutput $prepareOutput `
      -RedirectStandardError $prepareError
    if (Test-Path -LiteralPath $prepareOutput) {
        Get-Content -LiteralPath $prepareOutput | Add-Content -LiteralPath $resultPath
    }
    if ($assembly.ExitCode -ne 0) {
        if (Test-Path -LiteralPath $prepareError) {
            Get-Content -LiteralPath $prepareError | Add-Content -LiteralPath $resultPath
        }
        throw 'The root filesystem update could not be assembled. Nothing was written.'
    }
    if ((Get-Item -LiteralPath $imagePath).Length -ne $rootLength) {
        throw 'The prepared root image has the wrong size. Nothing was written.'
    }
    $imageHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $imagePath).Hash
    "PREPARED $imageHash" | Add-Content -LiteralPath $resultPath

    $mountedLetters = @(Get-Partition -DiskNumber $diskNumber |
        Where-Object { $_.DriveLetter } | ForEach-Object { [string]$_.DriveLetter })
    foreach ($letter in $mountedLetters) {
        & mountvol.exe ($letter + ':') /P
        if ($LASTEXITCODE -ne 0) { throw "Could not safely dismount seed volume $letter`: before writing." }
    }
    Start-Sleep -Seconds 2

    $source = [IO.FileStream]::new(
        $imagePath, [IO.FileMode]::Open, [IO.FileAccess]::Read,
        [IO.FileShare]::Read, $chunkSize, [IO.FileOptions]::SequentialScan)
    $target = [IO.FileStream]::new(
        $physicalPath, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite,
        [IO.FileShare]::ReadWrite, $chunkSize, [IO.FileOptions]::WriteThrough)
    $target.Position = $rootOffset
    $remaining = $rootLength
    while ($remaining -gt 0) {
        $wanted = if ($remaining -gt $chunkSize) { $chunkSize } else { [int]$remaining }
        $read = $source.Read($buffer, 0, $wanted)
        if ($read -ne $wanted) { throw 'Unexpected end of prepared root image.' }
        $target.Write($buffer, 0, $read)
        $remaining -= $read
    }
    $target.Flush($true)
    $target.Dispose(); $target = $null
    $source.Dispose(); $source = $null
    'WRITE 100%' | Add-Content -LiteralPath $resultPath

    Start-Sleep -Seconds 2
    $source = [IO.FileStream]::new(
        $physicalPath, [IO.FileMode]::Open, [IO.FileAccess]::Read,
        [IO.FileShare]::ReadWrite, $chunkSize, [IO.FileOptions]::SequentialScan)
    $source.Position = $rootOffset
    $remaining = $rootLength
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        while ($remaining -gt 0) {
            $wanted = if ($remaining -gt $chunkSize) { $chunkSize } else { [int]$remaining }
            $read = $source.Read($buffer, 0, $wanted)
            if ($read -ne $wanted) { throw 'Unexpected end of seed during readback verification.' }
            [void]$sha.TransformBlock($buffer, 0, $read, $buffer, 0)
            $remaining -= $read
        }
        [void]$sha.TransformFinalBlock((New-Object byte[] 0), 0, 0)
        $readbackHash = ([BitConverter]::ToString($sha.Hash)).Replace('-', '')
    }
    finally { $sha.Dispose() }
    if ($readbackHash -ne $imageHash) { throw "Root verification failed: $readbackHash" }
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
