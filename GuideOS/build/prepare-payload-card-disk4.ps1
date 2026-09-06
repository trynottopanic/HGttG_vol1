$ErrorActionPreference = 'Stop'

$diskNumber = 4
$expectedName = 'TS-RDF5 SD  Transcend'
$expectedSerial = '00000000TS38'
$expectedSize = 250399948800L
$partitionSize = 4GB
$sourceManifest = Join-Path $PSScriptRoot '..\examples\payload-card\GUIDE\PAYLOAD.GDE'
$resultPath = Join-Path $PSScriptRoot 'prepare-payload-card-result.txt'

Remove-Item -LiteralPath $resultPath -Force -ErrorAction SilentlyContinue

try {
    $disk = Get-Disk -Number $diskNumber
    if ($disk.FriendlyName -ne $expectedName -or
        $disk.SerialNumber.Trim() -ne $expectedSerial -or
        $disk.Size -ne $expectedSize -or
        $disk.BusType -ne 'USB' -or
        $disk.IsBoot -or $disk.IsSystem) {
        throw 'Disk 4 does not match the confirmed expendable 250 GB muOS card. Nothing was erased.'
    }
    if ($disk.IsReadOnly) {
        throw 'The confirmed payload card is write-protected. Nothing was erased.'
    }
    if (-not (Test-Path -LiteralPath $sourceManifest -PathType Leaf)) {
        throw 'The Guide payload example manifest is missing. Nothing was erased.'
    }

    Clear-Disk -Number $diskNumber -RemoveData -RemoveOEM -Confirm:$false
    $clearedDisk = Get-Disk -Number $diskNumber
    if ($clearedDisk.PartitionStyle -EQ 'RAW') {
        Initialize-Disk -Number $diskNumber -PartitionStyle MBR
    }
    $partition = New-Partition -DiskNumber $diskNumber -Size $partitionSize -AssignDriveLetter
    $volume = Format-Volume -Partition $partition -FileSystem FAT32 `
        -NewFileSystemLabel 'GUIDE_PAYLOAD' -Confirm:$false -Force

    $root = "{0}:\" -f $volume.DriveLetter
    $guideDirectory = Join-Path $root 'GUIDE'
    New-Item -ItemType Directory -Path $guideDirectory -Force | Out-Null
    $targetManifest = Join-Path $guideDirectory 'PAYLOAD.GDE'
    Copy-Item -LiteralPath $sourceManifest -Destination $targetManifest

    $written = Get-Content -LiteralPath $targetManifest -Raw
    $expected = Get-Content -LiteralPath $sourceManifest -Raw
    if ($written -ne $expected) {
        throw 'The payload manifest did not verify after copying.'
    }
    $manifestHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $targetManifest).Hash
    $verifiedDisk = Get-Disk -Number $diskNumber
    $verifiedPartition = Get-Partition -DiskNumber $diskNumber |
        Where-Object DriveLetter -EQ $volume.DriveLetter
    $verifiedVolume = Get-Volume -DriveLetter $volume.DriveLetter

    @(
        'PREPARED=TRUE'
        "DISK_NUMBER=$($verifiedDisk.Number)"
        "DISK_SIZE=$($verifiedDisk.Size)"
        "PARTITION_NUMBER=$($verifiedPartition.PartitionNumber)"
        "PARTITION_SIZE=$($verifiedPartition.Size)"
        "DRIVE_LETTER=$($verifiedVolume.DriveLetter)"
        "FILESYSTEM=$($verifiedVolume.FileSystem)"
        "LABEL=$($verifiedVolume.FileSystemLabel)"
        "MANIFEST=$targetManifest"
        "MANIFEST_SHA256=$manifestHash"
    ) | Set-Content -LiteralPath $resultPath -Encoding ascii
}
catch {
    "FAILED=$($_.Exception.Message)" | Set-Content -LiteralPath $resultPath -Encoding ascii
    throw
}
