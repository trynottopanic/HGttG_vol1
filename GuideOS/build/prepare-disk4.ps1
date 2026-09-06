$ErrorActionPreference = 'Stop'
$resultPath = "$PSScriptRoot\prepare-disk4-result.txt"

$disk = Get-Disk -Number 4
if ($disk.SerialNumber.Trim() -ne '00000000TS38' -or
    $disk.Size -ne 62239277056 -or
    $disk.BusType -ne 'USB' -or
    $disk.IsBoot -or $disk.IsSystem -or $disk.IsReadOnly) {
    throw 'Disk 4 no longer matches the confirmed writable Transcend microSD adapter.'
}

Clear-Disk -Number 4 -RemoveData -RemoveOEM -Confirm:$false
Update-Disk -Number 4
$disk = Get-Disk -Number 4
$partitions = @(Get-Partition -DiskNumber 4 -ErrorAction SilentlyContinue)
@(
    "PARTITION_STYLE=$($disk.PartitionStyle)"
    "IS_READ_ONLY=$($disk.IsReadOnly)"
    "IS_OFFLINE=$($disk.IsOffline)"
    "PARTITION_COUNT=$($partitions.Count)"
) | Set-Content -LiteralPath $resultPath -Encoding ASCII
