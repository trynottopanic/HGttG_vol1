$ErrorActionPreference = 'Stop'
$resultPath = "$PSScriptRoot\diagnose-disk4-result.txt"

$disk = Get-Disk -Number 4
if ($disk.SerialNumber.Trim() -ne '00000000TS38' -or
    $disk.Size -ne 62239277056 -or $disk.IsBoot -or $disk.IsSystem) {
    throw 'Disk 4 identity or safety state changed.'
}

$lines = @(
    "NUMBER=$($disk.Number)"
    "NAME=$($disk.FriendlyName)"
    "SERIAL=$($disk.SerialNumber.Trim())"
    "BUS=$($disk.BusType)"
    "SIZE=$($disk.Size)"
    "PARTITION_STYLE=$($disk.PartitionStyle)"
    "IS_READ_ONLY=$($disk.IsReadOnly)"
    "IS_OFFLINE=$($disk.IsOffline)"
    "OPERATIONAL_STATUS=$($disk.OperationalStatus -join ',')"
)

$partitions = @(Get-Partition -DiskNumber 4 -ErrorAction SilentlyContinue)
foreach ($partition in $partitions) {
    $accessPaths = @($partition.AccessPaths) -join ','
    $lines += "PARTITION=$($partition.PartitionNumber);LETTER=$($partition.DriveLetter);SIZE=$($partition.Size);TYPE=$($partition.Type);ACCESS_PATHS=$accessPaths"
}

$lines | Set-Content -LiteralPath $resultPath -Encoding ASCII
