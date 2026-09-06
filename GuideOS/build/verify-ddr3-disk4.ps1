$ErrorActionPreference = 'Stop'

$expectedModel = 'TS-RDF5 SD  Transcend'
$expectedSerial = '00000000TS38'
$expectedSize = 62239277056
$expectedHash = 'E397679AD14CA7DFE454F5F2E3ADF2B78ECC81B7B576CCFA263F0C3FB60C61E4'
$imageLength = 2215641088L
$resultPath = 'E:\DGttG\HGttG_vol1\GuideOS\build\verify-ddr3-disk4-result.txt'

$disk = Get-Disk -Number 4
if ($disk.FriendlyName -ne $expectedModel -or
    $disk.SerialNumber.Trim() -ne $expectedSerial -or
    $disk.Size -ne $expectedSize -or
    $disk.IsBoot -or $disk.IsSystem) {
    throw 'Disk 4 identity or safety state changed.'
}

$buffer = New-Object byte[] 4MB
$stream = $null
$sha = [Security.Cryptography.SHA256]::Create()
try {
    $stream = [IO.FileStream]::new(
        '\\.\PhysicalDrive4', [IO.FileMode]::Open, [IO.FileAccess]::Read,
        [IO.FileShare]::ReadWrite, 4MB, [IO.FileOptions]::SequentialScan)
    $remaining = $imageLength
    while ($remaining -gt 0) {
        if ($remaining -gt $buffer.Length) { $wanted = $buffer.Length }
        else { $wanted = [int]$remaining }
        $read = $stream.Read($buffer, 0, $wanted)
        if ($read -le 0) { throw 'Unexpected end of card during verification.' }
        [void]$sha.TransformBlock($buffer, 0, $read, $buffer, 0)
        $remaining -= $read
    }
    [void]$sha.TransformFinalBlock((New-Object byte[] 0), 0, 0)
    $actualHash = ([BitConverter]::ToString($sha.Hash)).Replace('-', '')
    @(
        "CARD_SHA256=$actualHash"
        "EXPECTED_SHA256=$expectedHash"
        "MATCH=$($actualHash -eq $expectedHash)"
    ) | Set-Content -LiteralPath $resultPath -Encoding ascii
    if ($actualHash -ne $expectedHash) { exit 2 }
}
finally {
    if ($stream) { $stream.Dispose() }
    $sha.Dispose()
}
