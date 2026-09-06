$ErrorActionPreference = 'Stop'

$diskNumber = 4
$expectedName = 'TS-RDF5 SD  Transcend'
$expectedSerial = '00000000TS38'
$expectedSize = 250399948800L
$resultPath = Join-Path $PSScriptRoot 'inspect-cartridge-card-result.txt'

$disk = Get-Disk -Number $diskNumber
if ($disk.FriendlyName -ne $expectedName -or
    $disk.SerialNumber.Trim() -ne $expectedSerial -or
    $disk.Size -ne $expectedSize -or
    $disk.BusType -ne 'USB' -or
    $disk.IsBoot -or $disk.IsSystem) {
    throw 'Disk 4 is not the expected removable cartridge card. Nothing was changed.'
}

$lines = @(
    'READ-ONLY CARTRIDGE CARD INSPECTION'
    "Disk=$($disk.Number)"
    "Name=$($disk.FriendlyName)"
    "Serial=$($disk.SerialNumber.Trim())"
    "Bytes=$($disk.Size)"
    "Style=$($disk.PartitionStyle)"
)

foreach ($partition in Get-Partition -DiskNumber $diskNumber | Sort-Object PartitionNumber) {
    $volume = $partition | Get-Volume -ErrorAction SilentlyContinue
    $letter = if ($partition.DriveLetter) { "$($partition.DriveLetter):" } else { '(none)' }
    $filesystem = if ($volume) { $volume.FileSystem } else { '(none)' }
    $label = if ($volume) { $volume.FileSystemLabel } else { '(none)' }
    $health = if ($volume) { $volume.HealthStatus } else { '(none)' }
    $lines += "Partition=$($partition.PartitionNumber) Offset=$($partition.Offset) Bytes=$($partition.Size) Drive=$letter FileSystem=$filesystem Label=$label Health=$health"
}

$lines | Set-Content -LiteralPath $resultPath -Encoding ASCII
