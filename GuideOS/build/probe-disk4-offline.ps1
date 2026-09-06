$ErrorActionPreference = 'Stop'
$resultPath = Join-Path $PSScriptRoot 'probe-disk4-offline-result.txt'
$diskNumber = 4
$expectedSerial = '00000000TS38'
$expectedSize = 62239277056

try {
    $disk = Get-Disk -Number $diskNumber
    if ($disk.SerialNumber.Trim() -ne $expectedSerial -or
        $disk.Size -ne $expectedSize -or
        $disk.BusType -ne 'USB' -or
        $disk.IsBoot -or $disk.IsSystem) {
        throw 'Disk 4 does not match the confirmed Transcend adapter.'
    }
    "BEFORE IsOffline=$($disk.IsOffline) IsReadOnly=$($disk.IsReadOnly) Partitions=$($disk.NumberOfPartitions)" | Set-Content -LiteralPath $resultPath
    if ($disk.IsReadOnly) { throw 'The card is write-protected.' }
    Set-Disk -Number $diskNumber -IsOffline $true
    $offline = Get-Disk -Number $diskNumber
    "OFFLINE IsOffline=$($offline.IsOffline)" | Add-Content -LiteralPath $resultPath
    Set-Disk -Number $diskNumber -IsOffline $false
    $online = Get-Disk -Number $diskNumber
    "AFTER IsOffline=$($online.IsOffline)" | Add-Content -LiteralPath $resultPath
    'PROBE_OK' | Add-Content -LiteralPath $resultPath
}
catch {
    try { Set-Disk -Number $diskNumber -IsOffline $false -ErrorAction SilentlyContinue } catch {}
    "PROBE_FAILED $($_.Exception.Message)" | Add-Content -LiteralPath $resultPath
    exit 1
}
