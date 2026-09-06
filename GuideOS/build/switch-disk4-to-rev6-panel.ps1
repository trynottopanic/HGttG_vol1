$ErrorActionPreference = 'Stop'

$resultPath = 'E:\DGttG\HGttG_vol1\GuideOS\build\switch-panel-result.txt'
$mountPath = 'Z:\'

try {
    $disk = Get-Disk -Number 4
    if ($disk.FriendlyName -ne 'TS-RDF5 SD  Transcend') {
        throw "Disk 4 model mismatch: $($disk.FriendlyName)"
    }
    if ($disk.SerialNumber.Trim() -ne '00000000TS38') {
        throw "Disk 4 serial mismatch: $($disk.SerialNumber)"
    }
    if ($disk.Size -ne 62239277056) {
        throw "Disk 4 size mismatch: $($disk.Size)"
    }
    if ($disk.IsBoot -or $disk.IsSystem) {
        throw 'Refusing to modify a boot or system disk.'
    }
    if (Test-Path -LiteralPath $mountPath) {
        throw 'Drive letter Z is already in use.'
    }

    Add-PartitionAccessPath -DiskNumber 4 -PartitionNumber 1 -AccessPath $mountPath
    Start-Sleep -Seconds 2

    $active = Join-Path $mountPath 'extlinux\extlinux.conf'
    $standard = Join-Path $mountPath 'extlinux\extlinux-standard.conf'
    $revision6 = Join-Path $mountPath 'extlinux\extlinux-rev6.conf'

    if (-not (Test-Path -LiteralPath $active)) {
        throw 'The active GuideOS configuration is missing.'
    }
    if (-not (Test-Path -LiteralPath $revision6)) {
        throw 'The revision-6 GuideOS configuration is missing.'
    }
    if ((Get-Content -LiteralPath $revision6 -Raw) -notmatch 'rev6-panel\.dtb') {
        throw 'The proposed configuration does not identify the revision-6 panel.'
    }

    if (-not (Test-Path -LiteralPath $standard)) {
        Copy-Item -LiteralPath $active -Destination $standard
    }
    Copy-Item -LiteralPath $revision6 -Destination $active -Force

    $activeHash = (Get-FileHash -LiteralPath $active -Algorithm SHA256).Hash
    $revision6Hash = (Get-FileHash -LiteralPath $revision6 -Algorithm SHA256).Hash
    if ($activeHash -ne $revision6Hash) {
        throw 'The active configuration did not verify after copying.'
    }

    Remove-PartitionAccessPath -DiskNumber 4 -PartitionNumber 1 -AccessPath $mountPath
    @(
        'STATUS=SUCCESS'
        'DISK=4'
        'PANEL=REVISION-6'
        "ACTIVE_SHA256=$activeHash"
        'UNMOUNTED=TRUE'
    ) | Set-Content -LiteralPath $resultPath -Encoding ascii
}
catch {
    try {
        if (Test-Path -LiteralPath $mountPath) {
            Remove-PartitionAccessPath -DiskNumber 4 -PartitionNumber 1 -AccessPath $mountPath -ErrorAction SilentlyContinue
        }
    } catch {}
    @(
        'STATUS=FAILED'
        "ERROR=$($_.Exception.Message)"
    ) | Set-Content -LiteralPath $resultPath -Encoding ascii
    exit 1
}
