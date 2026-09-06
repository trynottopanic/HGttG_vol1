$ErrorActionPreference = 'Stop'

$diskNumber = 4
$expectedName = 'TS-RDF5 SD  Transcend'
$expectedSerial = '00000000TS38'
$expectedSize = 62239277056L
$imagePath = 'G:\GuideOS-private\muos-reference\seed-wifi-ui-font-reconnect-shutdown-rootfs.ext4'
$expectedImageHash = 'DBE8103109720E29E2D4F72E45FB711146176898726AB06627624106D6DBF017'
$rootOffset = 163577856L
$rootLength = 2147483648L
$physicalPath = '\\.\PhysicalDrive4'
$resultPath = Join-Path $PSScriptRoot 'flash-private-wifi-ui-rootfs-result.txt'

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
        throw 'Disk 4 does not match the confirmed 64 GB GuideOS seed. Nothing was written.'
    }
    if ($disk.IsReadOnly) { throw 'The seed is write-protected. Nothing was written.' }
    if ((Get-Item -LiteralPath $imagePath).Length -ne $rootLength) {
        throw 'The Wi-Fi UI root image size changed. Nothing was written.'
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $imagePath).Hash -ne $expectedImageHash) {
        throw 'The Wi-Fi UI root image checksum changed. Nothing was written.'
    }

    $mountedLetters = @(Get-Partition -DiskNumber $diskNumber |
        Where-Object { $_.DriveLetter } |
        ForEach-Object { [string]$_.DriveLetter })
    foreach ($letter in $mountedLetters) {
        & mountvol.exe ($letter + ':') /P
        if ($LASTEXITCODE -ne 0) {
            throw "Could not safely dismount seed volume $letter`: before writing."
        }
    }
    Start-Sleep -Seconds 2

    $chunkSize = 4MB
    $buffer = New-Object byte[] $chunkSize
    $source = [IO.FileStream]::new(
        $imagePath, [IO.FileMode]::Open, [IO.FileAccess]::Read,
        [IO.FileShare]::Read, $chunkSize, [IO.FileOptions]::SequentialScan)
    $target = [IO.FileStream]::new(
        $physicalPath, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite,
        [IO.FileShare]::ReadWrite, $chunkSize, [IO.FileOptions]::WriteThrough)
    $target.Position = $rootOffset
    $remaining = $rootLength
    $written = 0L
    $nextReport = 10
    while ($remaining -gt 0) {
        if ($remaining -gt $chunkSize) { $wanted = $chunkSize }
        else { $wanted = [int]$remaining }
        $read = $source.Read($buffer, 0, $wanted)
        if ($read -ne $wanted) { throw 'Unexpected end of Wi-Fi UI root image.' }
        $target.Write($buffer, 0, $read)
        $remaining -= $read
        $written += $read
        $complete = [int][Math]::Floor(100 * $written / $rootLength)
        if ($complete -ge $nextReport -and $nextReport -lt 100) {
            "WRITE $complete%" | Add-Content -LiteralPath $resultPath
            $nextReport += 10
        }
    }
    $target.Flush($true)
    $target.Dispose()
    $target = $null
    $source.Dispose()
    $source = $null
    'WRITE 100%' | Add-Content -LiteralPath $resultPath

    Start-Sleep -Seconds 2
    $target = [IO.FileStream]::new(
        $physicalPath, [IO.FileMode]::Open, [IO.FileAccess]::Read,
        [IO.FileShare]::ReadWrite, $chunkSize, [IO.FileOptions]::SequentialScan)
    $target.Position = $rootOffset
    $remaining = $rootLength
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        while ($remaining -gt 0) {
            if ($remaining -gt $chunkSize) { $wanted = $chunkSize }
            else { $wanted = [int]$remaining }
            $read = $target.Read($buffer, 0, $wanted)
            if ($read -le 0) { throw 'Unexpected end of card during verification.' }
            [void]$sha.TransformBlock($buffer, 0, $read, $buffer, 0)
            $remaining -= $read
        }
        [void]$sha.TransformFinalBlock((New-Object byte[] 0), 0, 0)
        $rootHash = ([BitConverter]::ToString($sha.Hash)).Replace('-', '')
    }
    finally {
        $sha.Dispose()
    }
    if ($rootHash -ne $expectedImageHash) { throw "Root verification failed: $rootHash" }
    "VERIFIED $rootHash" | Add-Content -LiteralPath $resultPath
}
catch {
    "FAILED $($_.Exception.Message)" | Add-Content -LiteralPath $resultPath
    throw
}
finally {
    if ($source) { $source.Dispose() }
    if ($target) { $target.Dispose() }
}
