$ErrorActionPreference = 'Stop'
$resultPath = "$PSScriptRoot\enumerate-disks-result.txt"
Get-Disk |
    Sort-Object Number |
    Select-Object Number,FriendlyName,SerialNumber,BusType,Size,PartitionStyle,IsBoot,IsSystem,IsReadOnly,IsOffline,OperationalStatus |
    Format-List |
    Out-String -Width 240 |
    Set-Content -LiteralPath $resultPath -Encoding ASCII
