$ErrorActionPreference = 'Stop'
$resultPath = "$PSScriptRoot\diskpart-clean4-result.txt"
$commandsPath = "$PSScriptRoot\diskpart-clean4.txt"

$disk = Get-Disk -Number 4
if ($disk.SerialNumber.Trim() -ne '00000000TS38' -or
    $disk.Size -ne 62239277056 -or
    $disk.BusType -ne 'USB' -or
    $disk.IsBoot -or $disk.IsSystem) {
    throw 'Disk 4 identity or safety state changed.'
}

$diskpartOutput = (& diskpart.exe /s $commandsPath 2>&1 | Out-String -Width 240)
Start-Sleep -Seconds 2
Update-Disk -Number 4 -ErrorAction SilentlyContinue
$after = Get-Disk -Number 4
$partitions = @(Get-Partition -DiskNumber 4 -ErrorAction SilentlyContinue)
@(
    $diskpartOutput
    "AFTER_PARTITION_STYLE=$($after.PartitionStyle)"
    "AFTER_IS_READ_ONLY=$($after.IsReadOnly)"
    "AFTER_PARTITION_COUNT=$($partitions.Count)"
) | Set-Content -LiteralPath $resultPath -Encoding ASCII
